# Input and map file paths
v101FilePath = "v101_cleaned.txt"
mapFilePath = "mapping.txt"

# Setup foundChars array
foundChars = []

# Find characters in the input file and save to foundChars
with open(v101FilePath, "r") as v101File:

  for char in v101File.read():

    if not char in foundChars:
      foundChars.append(char)

# Wipe map file
mapFile = open(mapFilePath, "w")
mapFile.close()

# For each character in foundChars, write the character into the map file
with open(mapFilePath, "a") as mapFile:

  i = 0
  for char in foundChars:

    # Skips input file delimiters
    if char == "\n" or char == "." or char == ",":
      i = i - 1
    else:
      mapFile.write(str(i) + "=" + char + "~" + char + "\n")
    
    i = i + 1
