# The Voynich Transliteration Tool (TVTT)
Create your own Voynich Manuscript transliteration or translation based on the v101 transliteration.

## Goal:
  &emsp;To make a program that replaces each character in the v101 transcription of the Voynich Manuscript with a customizable corresponding mapping of v101 characters to the characters you set. The program should optionally account for scribal abbreviation in the Voynich Manuscript and the possibility of a single Voynich Manuscript character corresponding to multiple characters.

## Features:
  - Positional context mapping at the front and end of words using syntax (see below).
  - Multi-character input and output mapping (Eg. "55=4o" for number_mapping.txt and "55=con" for output_mapping.txt)
  - Syntax features for functionality purposes. (Note: The same character can be mapped multiple times if you have different syntax on each line.)

## Tutorial:
  **NOTE:** Do not touch v101.txt and v101_cleaned.txt! (Although the v101_cleaned.txt file can be extremly useful for other use cases as it gets rid of the < and > characters and everything inside of them. Feel free to download that just that file for your own use.)<br />
  
  **NOTE:** Each mapping must be on a new line for both number_mapping.txt and output_mapping.txt!

  ### Syntax: 
  (Note: Special syntax only works in the number_mapping.txt file, not the output_mapping.txt file.)<br />
  - @ at the end of a line in the number_mapping.txt file means the program will use that mapping number if the character is at the start of a word (E.g. "56=9@" only uses that mapping if 9 is at the front of a word). 
  - / at the end of a line in the number_mapping.txt file means the program will use that mapping number if the character is at the end of a word (E.g. "57=9/" only uses that mapping if 9 is at the end of a word).
  - ) at the beginning of a line in the output_mapping.txt file means that line will be ignored (Essentially commented out) (E.g. ")58=9" ignores that line completely).
  - Having no special syntax in the line just works normally for any position in a word (Note: The same character can be mapped multiple times if you have different syntax on each line) (E.g. "58=9" uses that mapping if "9" is anywhere in the word.)

  ### Instructions:
  
  &emsp;1. Download the .zip file from the latest release and unpack it. Then navigate to the directory you unpacked the files to.<br />
  
  &emsp;2. Open the number_mapping.txt file and edit it (Mappings can be mulitple letters corrosponding to one number, Eg. "60=4o") (You can optionally use special syntax, Eg. "59=9/") (Note: Do not delete or change the already existing lines, add new ones for multi-character mapping and special syntax.)<br />
  
  &emsp;3. Open and remap the output_mapping.txt file with the corosponding output character(s) (Optionally can be mulitple letters, Eg. "59=us") (Note: Only change the characters in the mapping, not the numbers. If you have added lines to number_mapping.txt then you should add the corrosonding lines with the correct numbers, otherwise those character mappings will be ignored. Also, mappings in output_mapping.txt will be ignored if there is no corresonding mapping in number_mapping.txt and vice versa.)<br />
  
  &emsp;4. Run the main.py program and open the output.txt file to see your transliteration (Using the examples above, setting "59=9/" in the number_mapping.txt and "59=us" in the output_mapping.txt file will replace all the "9" characters at the end of words with "us" in the output.txt file) (Note: # characters are spaces and , characters are ambiguous spaces. This can be changed in output_mapping.txt.)

## Final notes:
  &emsp;Thanks for checking this tool out! If you have feature requests or ideas, please open an issue of the category: "Feature/improvement request"! If you have a bug to report, please open an issue of the category: "Bug report"! This project is a work in progress and I'd love suggestions!
