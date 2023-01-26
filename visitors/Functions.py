from .LocalVariables import LocalVariableExtraction
from generators.LocalMemoryAllocation import LocalMemoryAllocation
from generators.FunctionGenerator import FunctionGenerator
import ast

LabeledInstruction = tuple[str, str]
assigned = {}

class Functions(ast.NodeVisitor):
     def __init__(self, st) -> None:
          super().__init__()
          self.__instructions = list()
          self.__should_save = True
          self.__current_variable = None
          self.__elem_id = 0
          self.__num_of_params = 0
          self.__num_of_local_vars = 0
          self.__func_count = 0
          self.st = st
          self.__in_func = False

     """We supports assignments and input/print calls"""
    
     def finalize(self):
          return self.__instructions

     def printHeader(self, local_extractor, node):
          function_def = f'; *** {node.name}('
          for arg in node.args.args:
               function_def += f'{arg.arg}, '
          if ', ' in function_def:
               function_def = function_def[0:-2]
          function_def += ')'
          if (local_extractor.returnExists):
               print(function_def + ' -> int function definition')
          else:
               print(function_def + ' function definition')

     def visit_FunctionDef(self, node):
          # define memory
          self.__in_func = True
          local_extractor = LocalVariableExtraction(self.st)
          local_extractor.visit(node)
          self.__num_of_local_vars = len(local_extractor.local_vars)
          self.__num_of_params = len(local_extractor.parameters)
          local_memory_alloc = LocalMemoryAllocation(local_extractor.local_vars, local_extractor.parameters, self.st)
          self.printHeader(local_extractor, node)
          local_memory_alloc.generate(self.__func_count)

          # Visiting the body of the function
          self.__record_instruction(f'SUBSP {(self.__num_of_local_vars)*2},i\t; Push local vars', label = f'{node.name}')
          for contents in node.body:
               self.visit(contents)

          # if no visit return occured, we must add return here
          if not local_extractor.returnExists:
               self.__record_instruction(f'ADDSP {(self.__num_of_local_vars)*2},i\t; Pop local vars')
               self.__record_instruction(f'RET')
          
          # Print each function after its visited for formatting
          fg = FunctionGenerator(self.finalize())
          fg.generate()
          
          # Reset stuff for next function
          self.__func_count += 1      
          self.__in_func = False 
          self.__instructions = list()

     def visit_Return(self,node):
          if not self.__in_func: return

          # Return constant
          if isinstance(node.value,ast.Constant):
               self.__instructions.append((None, f'LDWA {node.value.value},i'))
          # anything else is stored on the stack
          else:
               self.__instructions.append((None, f'LDWA {self.st.getLocalName(node.value.id, self.__func_count)},s'))

          # Loc of return val = 2*num_of_loc_vars + 2*num_of_params + 2{return value}
          self.__instructions.append((None, f'STWA {self.__num_of_local_vars * 2 + self.__num_of_params * 2 + 2},s'))
          
          # pop local vars
          self.__instructions.append((None, f'ADDSP {(self.__num_of_local_vars)*2},i\t; Pop local vars'))

          self.__instructions.append((None, f'RET'))

     def visit_Assign(self, node):
          if not self.__in_func: return
          # remembering the name of the target
          self.__current_variable = self.st.getLocalName(node.targets[0].id,self.__func_count)
          
          # visiting the left part, now knowing where to store the result
          self.__in_assign = True
          self.visit(node.value)
          self.__in_assign = False

          if self.__should_save:
               self.__record_instruction(f'STWA {self.__current_variable},s')
          else:
               self.__should_save = True
          self.__current_variable = None

     def visit_Constant(self, node):
          if not self.__in_func: return
          self.__record_instruction(f'LDWA {node.value},i')
    
     def visit_Name(self, node):
          if not self.__in_func: return
          self.__record_instruction(f'LDWA {self.st.getLocalName(node.id,self.__func_count)},s')

     def visit_BinOp(self, node):
          if not self.__in_func: return
          self.__access_memory(node.left, 'LDWA')
          if isinstance(node.op, ast.Add):
               self.__access_memory(node.right, 'ADDA')
          elif isinstance(node.op, ast.Sub):
               self.__access_memory(node.right, 'SUBA')
          else:
               raise ValueError(f'Unsupported binary operator: {node.op}')

     def visit_Call(self, node):
        if not self.__in_func: return
        match node.func.id:
            case 'int': 
                # Let's visit whatever is casted into an int
                self.visit(node.args[0])
            case 'input':
                # We are only supporting integers for now
                self.__record_instruction(f'DECI {self.__current_variable},s')
                self.__should_save = False # DECI already save the value in memory
            case 'print':
                # We are only supporting integers for now
                self.__record_instruction(f'DECO {self.st.getLocalName(node.args[0].id,self.__func_count)},s')
                self.__record_instruction("LDBA '\\n',i")
                self.__record_instruction('STBA charOut,d')

            case _:
                # for each item argument passed in, load it
                counter = 0
                for arg in node.args:
                    self.__record_instruction(f'; Begin Loading {arg.value if isinstance(arg,ast.Constant) else self.st.getLocalName(arg.id,self.__func_count)} to the stack')
                    self.__access_memory(arg, 'LDWA')
                    # When calling a function in another function, we must move the stack pointer up after loading the value
                    # because the loc of out vars is dependant on the stack pointer
                    self.__record_instruction(f'SUBSP {len(node.args) * 2 + (2 if self.__in_assign else 0)},i')
                    self.__record_instruction(f'STWA {counter},s')
                    counter += 2
                    self.__record_instruction(f'ADDSP {len(node.args) * 2 + (2 if self.__in_assign else 0)},i')
                    self.__record_instruction(f'; Finished Loading {arg.value if isinstance(arg,ast.Constant) else self.st.getLocalName(arg.id,self.__func_count)} to the stack')

                # if in assign, sub 2 for retVal
                self.__record_instruction(f'SUBSP {len(node.args) * 2 + (2 if self.__in_assign else 0)},i\t; Moving SP for local vars and pushing Ret Val')
                self.__record_instruction(f'CALL {node.func.id}')
                if len(node.args) > 0: self.__record_instruction(f'ADDSP {len(node.args) * 2},i\t; Popping local vars')
                
                if self.__in_assign:
                    self.__record_instruction(f'LDWA 0,s')
                    self.__record_instruction(f'ADDSP 2,i\t; Pop ret val')

    ####
    ## Handling While loops (only variable OP variable)
    ####

     def visit_While(self, node):
        if not self.__in_func: return
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
        for contents in node.body:
            self.visit(contents)
        self.__record_instruction(f'BR test_{loop_id}')
        # Sentinel marker for the end of the loop
        self.__record_instruction(f'NOP1', label = f'end_l_{loop_id}')
    
    ####
    ## Handling If statements
    ####

     def visit_If(self, node):
        if not self.__in_func: return
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
    ## Helper functions to 
    ####

     def __record_instruction(self, instruction, label = None):
        self.__instructions.append((label, instruction))
 
     def __access_memory(self, node, instruction, label = None):
        if isinstance(node, ast.Constant):
            self.__record_instruction(f'{instruction} {node.value},i', label)

        # If node passed in is a name and global constant
        elif (isinstance(node, ast.Name) and node.id[0] == "_" and node.id.isupper()):
            self.__record_instruction(f'{instruction} {self.st.getLocalName(node.id,self.__func_count)},i', label)

        else:
            self.__record_instruction(f'{instruction} {self.st.getLocalName(node.id,self.__func_count)},s', label)

     def __identify(self):
        result = self.__elem_id
        self.__elem_id = self.__elem_id + 1
        return result

     
