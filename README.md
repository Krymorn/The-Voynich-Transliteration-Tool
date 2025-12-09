# The Voynich Transliteration Tool (TVTT)
Create your own Voynich Manuscript transliteration based on the v101 transcription.

## Overview:
  &emsp;TVTT is a program that replaces each character in the v101 transcription of the Voynich Manuscript with a customizable, user-defined mapping of v101 characters to the characters you set. The program should optionally account for scribal abbreviation in the Voynich Manuscript and the possibility of a single Voynich Manuscript character corresponding to multiple characters.

## Features:
  - Positional context mapping at the front and end of words using syntax (see below).
  - Multi-character input and output mapping (e.g. `55=4o~con` in `mapping.txt`.)
  - Frequency and 
  - Syntax features for functionality purposes. (Note: The same character can be mapped multiple times if you have different syntax on each line. Also, if there is only a single character in a word and the character has multiple mappings, the first mapping will be used)

## Tutorial:

  ### File Uses:
  - `cleaner.py` cleans the v101 transcription from `v101.txt` and puts it in `v101_cleaned.txt`.
  - `mapping.py` sets the default mappings in `mapping.txt` by scanning through `v101_cleaned.txt` and adding new characters to the mapping file.
  - `mapping.txt` contains the mapping to convert v101 characters into numeric placeholders and then back into your custom mapping.<br />
  - `main.py` uses `mapping.txt` to write to the `output_numbers.txt` file and then uses the `output_numbers.txt` file to write your custom mapping to `output.txt`.
  - `output.txt` contains the outputted transcription with your transliteration.
  - `analysis.txt` contains the analysis of the character frequency and character entropy of the `output.txt` file.

  **NOTE:** Do not touch `v101.txt` and `v101_cleaned.txt`! (Although the `v101_cleaned.txt` file can be extremely useful for other use cases as it gets rid of the `<` and `>` characters and everything inside of them. Feel free to download just that file for your own use.)<br />
  
  **NOTE:** Each mapping must be on a new line in `mapping.txt`!<br>

  ### Syntax: 
  - `@`  —  at the end of a line means the program will use that mapping number if the character is at the start of a word (e.g. `56=9@` only uses that mapping if `9` is at the front of a word). 
  - `/`  —  at the end of a line means the program will use that mapping number if the character is at the end of a word (e.g. `57=9/` only uses that mapping if `9` is at the end of a word).
  - `)`  —  at the beginning of a line means that line will be ignored (Essentially commented out) (e.g. `)58=9~us` ignores that line completely).
  - Having no special syntax in the line just works normally for any position in a word (Note: The same character can be mapped multiple times if you have different syntax on each line) (e.g. `58=9~us` uses that mapping for `9` if it is anywhere in the current word.)

  ### Instructions:
  
  &emsp;1. Download the `.zip` file from the latest release and unpack it. Then navigate to the directory you unpacked the files to.<br />
  
  &emsp;2. Open and remap the `mapping.txt` file as needed with the corresponding output character(s) (Optionally can be multiple letters, e.g. `59=9~us`) (Note: Do not delete or change anything before the `~` (e.g. `59=9~changeThis`.)<br />
  
  &emsp;3. Run the main.py program and open the `output.txt` file to see your transliteration (Using the examples above, setting `60=9~us/` in `mapping.txt` file will replace all the `9` characters at the end of words with `us` in the `output.txt` file)

  &emsp;4. Optionally, if you have it enabled, open `analysis.txt` and see the statistical analysis of `output.txt`.

### How it works:
`v101_cleaned.txt` → `mapping.txt` → `output_numbers.txt` → `output.txt` → `analysis.txt`

## FAQ:

**Q: What is v101?**  
A: v101 is one of the standard transcription systems for representing Voynich Manuscript characters in a text format.

**Q: Is this a translation tool?**  
A: No. This is a transliteration tool, not a translation engine. It remaps the Voynich Manuscript characters into user-defined characters or strings.

**Q: Can one Voynich character map to multiple input and/or output characters?**<br>
A: Yes. The tool supports both multi-character input and output (e.g. `59=4o~con`).

**Q: Can different mappings apply depending on where a character appears in a word?**<br>
A: Yes. By default, use:
- `@` for start of word
- `/` for end of word

**Q: Can this help decode the Voynich Manuscript?**<br>
A: It is not a decoding solution by itself, but it can assist researchers in testing substitution schemes and hypotheses.

**Q: Why are `=` and `-` in the output?**<br>
A: By default:
- `=` = space
- `-` = ambiguous space

**Q: What do the analysis tools do?**<br>
A: If enabled, the analysis tools will calculate the character frequency and character entropy in `output.txt` and save the analysis to `analysis.txt`.

**Q: Can I change the delimiters and symbol configuration?**<br>
A: Yes. At the top of `main.py` you can change the delimiters and symbols. Although it is recommended to keep the defaults as they are tested and compatible with the v101 transcription. You can also change the space and ambiguous space characters in `mapping.py`.

**Q: Does it support languages other than English?**<br>
A: Yes. You can map the output to *any* characters or symbols supported by `.txt` files, including other languages and custom alphabets.

## Planned Features:

These features are being considered for future versions of TVTT:

- Batch processing of multiple texts
- Pattern and syllable distributon analysis
- Morphological decomposition tools
- Dictionary assisted mapping suggestions (maybe even ML at some point)
- Visualization of character frequency before/after mapping
- Option to use the EVA (or an alternative) transcription instead of the v101 transcription

Suggestions for new features are welcome — feel free to open an issue.

## Feedback & Ideas:
Thanks for checking this tool out! If you have a feature request, improvement idea, or find a bug, feel free to open an issue. This project is still a work in progress, and all suggestions are welcome.

## Credits & Citations:
&emsp;1. Voynich.nu for the copy of the v101 transcription. (https://voynich.nu/data/voyn_101.txt)<br>
&emsp;2. ChatGPT for assistance with bugs in the code and some of the documentation. (https://chatgpt.com/)<br>
&emsp;3. Google Gemini for the `cleaner.py` script and some minor bug fixes. (https://gemini.google.com/)
