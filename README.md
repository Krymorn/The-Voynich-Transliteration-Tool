# The Voynich Transcription Tool (TVTT)
Create your own Voynich Manuscript transcription or translation based on the v101 transcription.

## Goal:
  &emsp;To make a program that replaces each character in the v101 transcription of the Voynich Manuscript with a customizable corresponding mapping of v101 characters to the characters you set. The program should optionally account for scribal abbreviation in the Voynich Manuscript and the possibility of a single Voynich Manuscript character corresponding to multiple characters.

## Features:
  - Positional context mapping at the front and end of words using syntax (see below).
  - Multi-character input and output mapping (Eg. "55=4o" for number_mapping.txt and "55=con" for output_mapping.txt)
  - Syntax features for functionality purposes. (Note: The same character can be mapped multiple times if you have different syntax on each line.)

## Tutorial:
  **NOTE:** Do not touch v101.txt and v101_cleaned.txt! (Although the v101_cleaned.txt file can be extremly useful for other techniques as it gets rid of the <> page and line numbers.)<br />
  **NOTE:** Each mapping must be on a new line!

  ### Syntax: 
  (Note: Special syntax only works in the number_mapping.txt file, not the output_mapping.txt file.)<br />
  - @ at the end of a line in the number_mapping.txt file means the program will use that mapping number if the character is at the start of a word (E.g. "56=9@" only uses that mapping if 9 is at the front of a word). 
  - / at the end of a line in the number_mapping.txt file means the program will use that mapping number if the character is at the end of a word (E.g. "57=9/" only uses that mapping if 9 is at the end of a word).
  - ) at the beginning of a line in the number_mapping.txt file means that line will be ignored (Essentially commented out) (E.g. ")58=9" ignores that line completely).
  - Having no special syntax in the line just works normally for any position in the transcription (Note: The same character can be mapped multiple times if you have different syntax on each line) (E.g. "58=9" uses that mapping if "9" is anywhere in the word.)

  ### Instructions:
  
  &emsp;1. Remap the number_mapping.txt file for each v101.txt transcription character (Can be mulitple letters corrosponding to one number, Eg. "60=4o") (Optionally using the special syntax, Eg. "59=9/")<br />
  
  &emsp;2. Remap the output_mapping.txt file with the corosponding output letter(s) (Can be mulitple letters, Eg. "59=us")<br />
  
  &emsp;3. Run the main.py program and open the output.txt file to see your transcription (Using the examples above, setting "59=9/" in the number_mapping.txt and "59=us" in the output_mapping.txt file will replace all the "9" characters at the end of words with "us" in the output.txt file.)

## Notes:
  &emsp;Thanks for checking this tool out (or at least reading this post)! If you have feature requests or ideas, please comment! This is a work in progress and I'd love suggestions!
