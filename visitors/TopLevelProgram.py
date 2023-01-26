import ast

LabeledInstruction = tuple[str, str]
assigned = {}

class TopLevelProgram(ast.NodeVisitor):
    """We supports assignments and input/print calls"""
    
    def __init__(self, entry_point, st) -> None:
        super().__init__()
        self.__instructions = list()
        self.__record_instruction('NOP1', label=entry_point)
        self.__should_save = True
        self.__current_variable = None
        self.__elem_id = 0
        self.__in_loop = False
        self.__in_assign = False
        self.st = st

    def finalize(self):
        self.__instructions.append((None, '.END'))
        return self.__instructions

    ####
    ## Handling Assignments (variable = ...)
    ####

    def visit_Assign(self, node):
        # remembering the name of the target
        self.__current_variable = self.st.getName(node.targets[0].id)
        # visiting the left part, now knowing where to store the result
        if self.__in_loop or self.__current_variable in assigned or not isinstance(node.value, ast.Constant):
            self.__in_assign = True
            self.visit(node.value)
            self.__in_assign = False
            if self.__should_save:
                self.__record_instruction(f'STWA {self.__current_variable},d')
            else:
                self.__should_save = True
            self.__current_variable = None
        else:
            assigned[self.__current_variable] = True

    def visit_Constant(self, node):
        self.__record_instruction(f'LDWA {node.value},i')
    
    def visit_Name(self, node):
        self.__record_instruction(f'LDWA {self.st.getName(node.id)},d')

    def visit_BinOp(self, node):

        self.__access_memory(node.left, 'LDWA')
        if isinstance(node.op, ast.Add):
            self.__access_memory(node.right, 'ADDA')
        elif isinstance(node.op, ast.Sub):
            self.__access_memory(node.right, 'SUBA')
        else:
            raise ValueError(f'Unsupported binary operator: {node.op}')

    def visit_Call(self, node):
        match node.func.id:
            case 'int': 
                # Let's visit whatever is casted into an int
                self.visit(node.args[0])
            case 'input':
                # We are only supporting integers for now
                self.__record_instruction(f'DECI {self.__current_variable},d')
                self.__should_save = False # DECI already save the value in memory
            case 'print':
                # We are only supporting integers for now
                self.__record_instruction(f'DECO {self.st.getName(node.args[0].id)},d')
                self.__record_instruction("LDBA '\\n',i")
                self.__record_instruction('STBA charOut,d')

            case _:
                # function with input
                if self.__in_assign:
                    self.__record_instruction(f'SUBSP 2,i \t ; for retVal')

                if len(node.args) > 0:
                    counter = 0
                    self.__record_instruction(f'SUBSP {len(node.args) * 2},i')
                    for arg in node.args:
                        self.__access_memory(arg, 'LDWA')
                        self.__record_instruction(f'STWA {counter},s')
                        counter += 2
                self.__record_instruction(f'CALL {node.func.id}')
                    
                if len(node.args) > 0: self.__record_instruction(f'ADDSP {len(node.args) * 2},i')
                
                if self.__in_assign:
                    self.__record_instruction(f'LDWA 0,s')
                    self.__record_instruction(f'ADDSP 2,i')

    ####
    ## Handling While loops (only variable OP variable)
    ####

    def visit_While(self, node):
        loop_id = self.__identify()
        inverted = {
            ast.Lt:  'BRGE', # '<'  in the code means we branch if '>=' 
            ast.LtE: 'BRGT', # '<=' in the code means we branch if '>' 
            ast.Gt:  'BRLE', # '>'  in the code means we branch if '<='
            ast.GtE: 'BRLT', # '>=' in the code means we branch if '<'
            ast.NotEq: 'BREQ', # '!=' in the code means we branch if '=='
            ast.Eq: 'BRNE', # '==' in the code means we branch if '!='
        }
        # left part can only be a variable
        self.__access_memory(node.test.left, 'LDWA', label = f'test_{loop_id}')
        # right part can only be a variable
        self.__access_memory(node.test.comparators[0], 'CPWA')
        # Branching is ifition is not true (thus, inverted)
        self.__record_instruction(f'{inverted[type(node.test.ops[0])]} end_l_{loop_id}')
        # Visiting the body of the loop
        self.__in_loop = True
        for contents in node.body:
            self.visit(contents)
        self.__in_loop = False
        self.__record_instruction(f'BR test_{loop_id}')
        # Sentinel marker for the end of the loop
        self.__record_instruction(f'NOP1', label = f'end_l_{loop_id}')
    
    ####
    ## Handling If statements
    ####

    def visit_If(self, node):
        if_id = self.__identify()
        inverted = {
            ast.Lt:  'BRGE', # '<'  in the code means we branch if '>=' 
            ast.LtE: 'BRGT', # '<=' in the code means we branch if '>' 
            ast.Gt:  'BRLE', # '>'  in the code means we branch if '<='
            ast.GtE: 'BRLT', # '>=' in the code means we branch if '<'
            ast.NotEq: 'BREQ', # '!=' in the code means we branch if '=='
            ast.Eq: 'BRNE', # '==' in the code means we branch if '!='
        }
        # left part can only be a variable
        self.__access_memory(node.test.left, 'LDWA', label = f'if_{if_id}')
        # right part can only be a variable
        self.__access_memory(node.test.comparators[0], 'CPWA')
        # Branching if condition is not true (thus, inverted)

        # if orelse contains another if, we branch to check its condition rather than ending
        if len(node.orelse) and type(node.orelse[0]) == ast.If:
            self.__record_instruction(f'{inverted[type(node.test.ops[0])]} if_{if_id+1}')
        
        # if orelse doesnt contain an if, but has a body it is the else statement and will 
        # branch to it if condition isnt met 
        elif node.orelse != []:
            self.__record_instruction(f'{inverted[type(node.test.ops[0])]} else_{if_id}')

        # if orelse is empty, we can branch to end if
        else:
            self.__record_instruction(f'{inverted[type(node.test.ops[0])]} end_if_{if_id}')
       
        # Visiting the body of the if statement
        for contents in node.body:
            self.visit(contents)

        # After completing contents of body, branch to end if
        self.__record_instruction(f'BR end_if_{if_id}')

        #Create else reference if needed
        if len(node.orelse) and type(node.orelse[0]) != ast.If:
            self.__record_instruction("NOP1", label = f'else_{if_id}')

        for contents in node.orelse:
            self.visit(contents)

        # Sentinel marker for the end of the if statement
        self.__record_instruction(f'NOP1', label = f'end_if_{if_id}')

    ####
    ## Not handling function calls 
    ####

    def visit_FunctionDef(self, node):
        """We do not visit function definitions, they are not top level"""
        pass

    ####
    ## Helper functions to 
    ####

    def __record_instruction(self, instruction, label = None):
        self.__instructions.append((label, instruction))

    def __access_memory(self, node, instruction, label = None):
        if isinstance(node, ast.Constant):
            self.__record_instruction(f'{instruction} {node.value},i', label)

        # If node passed in is a name and global constant
        elif (isinstance(node, ast.Name) and node.id[0] == "_" and node.id.isupper()):
            self.__record_instruction(f'{instruction} {self.st.getName(node.id)},i', label)

        else:
            self.__record_instruction(f'{instruction} {self.st.getName(node.id)},d', label)

    def __identify(self):
        result = self.__elem_id
        self.__elem_id = self.__elem_id + 1
        return result