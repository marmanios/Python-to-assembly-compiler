import ast

class LocalVariableExtraction(ast.NodeVisitor):
    """ 
        We extract all of the details related to local (function) assignments
    """
    
    def __init__(self, st) -> None:
        super().__init__()
        self.st = st
        self.returnExists = False
        self.local_vars = {}
        self.parameters = {}


    def visit_FunctionDef(self, node):
        # visits all of the nodes in the function body
        for contents in node.body:
            self.visit(contents)

        # find number of bytes needed to allocate for local variables on stack
        i = (len(self.local_vars) - 1) * 2

        # add 2 bytes for initial stack location of parameters
        paramIndex = i + 4

        # map variables to associated stack location
        for var in self.local_vars:
            self.local_vars[var] = i
            i -= 2

        # map variables to associated stack location
        for var in self.local_vars:
            self.local_vars[var] = i
            i -= 2

        # map parameters to associated stack location
        for arg in node.args.args:
            self.parameters[arg.arg] = paramIndex
            paramIndex += 2


    def visit_Assign(self, node):
        # only add to local variables if not already assigned and not a parameter
        if node.targets[0].id not in self.local_vars and node.targets[0].id not in self.parameters:
                self.local_vars[node.targets[0].id] = None
    

    def visit_If(self, node):

        for contents in node.body:
            self.visit(contents)

        for contents in node.orelse:
            self.visit(contents)
    

    def visit_While(self, node):
        
        for contents in node.body:
            self.visit(contents)
    
    
    def visit_Return(self, node):
        # check to determine if function contains return statement
        self.returnExists = True
