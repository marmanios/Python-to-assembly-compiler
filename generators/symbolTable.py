class Symbol():
      def __init__(self, name, is_global):
         self.name = name
         # self.__value = value
         self.is_global = is_global

class SymbolTable():
   def __init__(self):
      self.map = {}

   # Map var name to value in symbol table
   def insertVal(self, name: str, is_global: bool):
      temp = name
      # len <= 8, no need to change anything
      if len(temp) > 8:
         # if its too long, try removing vowels, if that removes 
         # too much, just splice it 
         vowels = ('a', 'e', 'i', 'o', 'u', "A", "E", "I", "O", "U")
         temp = ''.join([l for l in name if l not in vowels])
         if len(temp) <= 3:
            temp = name[0:8]
          
         # if removing vowels wasnt enough, splice it too
         elif len(temp) > 8:
            temp = temp[0:8]

      self.map[name] = Symbol(temp, is_global)
     
   # Return mapped val in symbol table
   def getName(self, variableName: str):
      if variableName in self.map:
         return self.map[variableName].name
      else:
         return variableName
   
   def getLocalName(self, variableName: str, funcID: int):
      if variableName[0] == "_" and variableName.isupper():
            return self.getName(variableName)

      if variableName in self.map:
         if len(self.map[variableName].name) >= 7:
            return f'{self.map[variableName].name[0:6]}_{funcID}'

         else:
            return f'{self.map[variableName].name}_{funcID}'

      else:
         if len(variableName) >= 7:
            return f'{variableName[0:6]}_{funcID}'

         else:
            return f'{variableName}_{funcID}'

   # def updateVal(self, variableName, value):
   #    if variableName in self.map:
   #       self.map[variableName].__value = value
                 
