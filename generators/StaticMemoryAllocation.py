
class StaticMemoryAllocation():

    def __init__(self, global_vars: dict()) -> None:
        self.__global_vars = global_vars

    def generate(self):
        print('; Allocating Global (static) memory')
        for n in self.__global_vars:
            # If variable is assigned to a constant
            if self.__global_vars[n] != None:
                # if variable is assigned to a global constant
                if (n[0] == "_" and n.isupper()):
                    print(f'{n+":":<9}\t.EQUATE {self.__global_vars[n]}')

                # non-global constant 
                else:
                    print(f'{n+":":<9}\t.WORD {self.__global_vars[n]}')
            else:
                print(f'{n+":":<9}\t.BLOCK 2') # reserving memory
