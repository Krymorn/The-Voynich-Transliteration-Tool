# The Voynich Transliteration Tool (TVTT)
Create your own Voynich Manuscript transliteration based on the v101 transcription.

## Goal:
  &emsp;To make a program that replaces each character in the v101 transcription of the Voynich Manuscript with a customizable, user-defined mapping of v101 characters to the characters you set. The program should optionally account for scribal abbreviation in the Voynich Manuscript and the possibility of a single Voynich Manuscript character corresponding to multiple characters.

## Features:
  - Positional context mapping at the front and end of words using syntax (see below).
  - Multi-character input and output mapping (e.g. `55=4o` in number_mapping.txt and `55=con` in output_mapping.txt)
  - Syntax features for functionality purposes. (Note: The same character can be mapped multiple times if you have different syntax on each line.)

## Tutorial:

  **File Uses:**<br />
&emsp;`number_mapping.txt` converts v101 characters into numeric placeholders.<br />
&emsp;`output_mapping.txt` converts those numbers into your final characters.

  **NOTE:** Do not touch `v101.txt` and `v101_cleaned.txt`! (Although the `v101_cleaned.txt` file can be extremely useful for other use cases as it gets rid of the < and > characters and everything inside of them. Feel free to download just that file for your own use.)<br />
  
  **NOTE:** Each mapping must be on a new line for both `number_mapping.txt` and `output_mapping.txt`!

  ### Syntax: 
  (Note: Special syntax only works in the `number_mapping.txt` file, not the `output_mapping.txt` file.)<br />
  - @  —  at the end of a line means the program will use that mapping number if the character is at the start of a word (e.g. `56=9@` only uses that mapping if 9 is at the front of a word). 
  - /  —  at the end of a line means the program will use that mapping number if the character is at the end of a word (e.g. `57=9/` only uses that mapping if 9 is at the end of a word).
  - )  —  at the beginning of a line means that line will be ignored (Essentially commented out) (e.g. `)58=9` ignores that line completely).
  - Having no special syntax in the line just works normally for any position in a word (Note: The same character can be mapped multiple times if you have different syntax on each line) (e.g. `58=9` uses that mapping if `9` is anywhere in the word.)

  ### Instructions:
  
  &emsp;1. Download the .zip file from the latest release and unpack it. Then navigate to the directory you unpacked the files to.<br />
  
  &emsp;2. Open the `number_mapping.txt` file and edit it (Mappings can be multiple letters corresponding to one number, e.g. `60=4o`) (You can optionally use special syntax, e.g. `59=9/`) (Note: Do not delete or change the already existing lines, add new ones for multi-character mapping and special syntax.)<br />
  
  &emsp;3. Open and remap the `output_mapping.txt` file as needed with the corresponding output character(s) (Optionally can be multiple letters, e.g. `59=us`) (Note: Only change the characters in the mapping, not the numbers. If you have added lines to number_mapping.txt then you should add the corresponding lines with the correct numbers, otherwise those character mappings will be ignored. Also, mappings in output_mapping.txt will be ignored if there is no corresponding mapping in number_mapping.txt and vice versa.)<br />
  
  &emsp;4. Run the main.py program and open the `output.txt` file to see your transliteration (Using the examples above, setting `59=9/` in the `number_mapping.txt` and `59=us` in the `output_mapping.txt` file will replace all the `9` characters at the end of words with `us` in the `output.txt` file) (Note: # characters are spaces and , characters are ambiguous spaces. This can be changed in output_mapping.txt.)

### How it works:
`v101_cleaned.txt` → `number_mapping.txt` → `output_numbers.txt` → `output_mapping.txt` → `output.txt`

## FAQ:

**Q: What is v101?**  
A: v101 is one of the standard transcription systems for representing Voynich Manuscript characters in a text format.

**Q: Is this a translation tool?**  
A: No. This is a transliteration tool, not a translation engine. It remaps Voynich characters into user-defined characters or strings.

**Q: Can one Voynich character map to multiple output characters?**  
A: Yes. The tool supports multi-character output (e.g. `59=us`).

**Q: Can different mappings apply depending on where a character appears in a word?**  
A: Yes. Use:
- `@` for start of word
- `/` for end of word  
These only work inside `number_mapping.txt`.

**Q: Can this help decode the Voynich Manuscript?**  
A: It is not a decoding solution by itself, but it can assist researchers in testing substitution schemes and hypotheses.

**Q: Why are `#` and `,` in the output?**  
A: By default:
- `#` = space  
- `,` = ambiguous space  

You can change these in `output_mapping.txt`.

**Q: Does it support languages other than English?**  
A: Yes. You can map the output to *any* characters or symbols supported by `.txt` files, including other languages and custom alphabets.

## Planned Features:

These features are being considered for future versions of TVTT:

- Preset mapping profiles (Latin, English, phonetic, etc.)
- Batch processing of multiple texts
- Pattern and frequency analysis tools
- Optional machine-learning-assisted mapping suggestions
- Visualization of character frequency before/after mapping
- Easier use of mapping files (possibly only using a single file for mapping)
- Custom delimiter & symbol configuration in one place
- Option to use the EVA (or an alternative) transcription instead of the v101 transcription

Suggestions for new features are welcome — feel free to open an issue.

## Feedback & Ideas:
Thanks for checking this tool out! If you have a feature request, improvement idea, or find a bug, feel free to open an issue. This project is still a work in progress, and all suggestions are welcome.
