# Input and map file paths
# Change to "v101_cleaned.txt" and "v101_mapping.txt" if you would like.
filePath = "eva_cleaned.txt"
mapFilePath = "eva_mapping.json"

# Setup foundChars array
foundChars = []

# Find characters in the input file and save to foundChars
with open(filePath, "r", encoding="utf-8") as file:

  for char in file.read():

    if not char in foundChars:
      foundChars.append(char)

foundChars.sort()

# Wipe map file
mapFile = open(mapFilePath, "w")
mapFile.close()

# For each character in foundChars, write the character into the map file
with open(mapFilePath, "w", encoding="utf") as mapFile:

  mapFile.write("{\n")
  
  for char in foundChars:

    # Skips input file delimiters and end of line delimters and other misilanious characters
    if char == "\n" or char == "." or char == "," or char == "\"" or char == "-" or char == "=":
      pass
    else:
      if char == "\\":
        mapFile.write("    \"\\" + char + "\": \"\\" + char + "\",\n")
      else:
        mapFile.write("    \"" + char + "\": \"" + char + "\",\n")

  mapFile.write("}")
