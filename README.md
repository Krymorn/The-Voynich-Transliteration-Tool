# The Voynich Transliteration Tool (TVTT)
Create your own Voynich Manuscript transliteration based on the v101 transcription.

## Overview:
  &emsp;TVTT is a program that replaces each character in the v101 transcription of the Voynich Manuscript with a customizable, user-defined mapping of v101 characters to the characters you set. The program can optionally account for scribal abbreviation in the Voynich Manuscript and the possibility of a single Voynich Manuscript character corresponding to multiple output characters. The program also analyses the output and saves it.

## Features:
  - Positional context mapping at the front and end of words using syntax (see below).
  - Multi-character input and output mapping (e.g. `54=9~con`, `55=am~d`, and `55=4o~to` all work in `mapping.txt`.)
  - Character frequency and entropy analysis.
  - Common prefix, suffix, and affix finding and analysis.
  - Translation attempts from the output file after transliteration.
  - Position-in-word mapping features. (Note: The same character can be mapped multiple times but if you have different syntax on each line. Also, if there is only a single character in a word and the character has multiple mappings, the first character mapping will be prioritized, then the last character mapping second, and then the normal mapping third.)

## Tutorial:

  ### File Uses:
  - `cleaner.py` cleans the v101 transcription from `v101.txt` and puts it in `v101_cleaned.txt`.
  - `mapping.py` sets the default mappings in `mapping.txt` by scanning through `v101_cleaned.txt` and adding new characters to the mapping file.
  - `mapping.txt` contains the mapping to convert v101 characters into numeric placeholders and then back into your custom mapping.<br />
  - `main.py` uses `mapping.txt` to write to the `output_numbers.txt` file and then uses the `output_numbers.txt` file to write your custom mapping to `output.txt`.
  - `output_numbers.txt` is an intermediary file for changing the transcription to use your mapping (The file gets overwritten every time `main.py` is run so there is no reason to change the file.)
  - `output.txt` contains the outputted transcription with your transliteration.
  - `analysis.txt` contains the analysis of the character frequency, character entropy, and common prefix/suffix/roots of the `output.txt` file.
  - `translated.txt` contains the attempted translation from `output.txt`.

  **NOTE:** Do not touch `v101.txt` and `v101_cleaned.txt`! (Although the `v101_cleaned.txt` file can be extremely useful for other use cases as it gets rid of the `<` and `>` characters and everything inside of them. Feel free to download just that file for your own use.)<br />
  
  **NOTE:** Each mapping must be on a new line in `mapping.txt`!<br>

  ### Syntax: 
  - `@`  —  at the end of a line means the program will use that mapping number if the character is at the start of a word (e.g. `56=9@` only uses that mapping if `9` is at the front of a word). 
  - `/`  —  at the end of a line means the program will use that mapping number if the character is at the end of a word (e.g. `57=9/` only uses that mapping if `9` is at the end of a word).
  - `)`  —  at the beginning of a line means that line will be ignored (Essentially commented out) (e.g. `)58=9~us` ignores that line completely).
  - Having no special syntax in the line just works normally for any position in a word (Note: The same character can be mapped multiple times if you have different syntax on each line) (e.g. `58=9~us` uses that mapping for `9` if it is anywhere in the current word.)

  ### Instructions:
  
  &emsp;1. Download the `.zip` file from the latest release and unpack it. Then navigate to the directory you unpacked the files to.<br />
  
  &emsp;2. Open and remap the `mapping.txt` file as needed with the corresponding output character(s) (Optionally can be multiple letters, e.g. `59=9~us`) (Note: Do not delete or change anything before the `~` (e.g. `60=9~changeThis`) unless you are commenting that line out.<br />
  
  &emsp;3. Run the main.py program and open the `output.txt` file to see your transliteration (Using the example above, setting `59=9~us/` in `mapping.txt` file will replace all the `9` characters at the end of words with `us` in the `output.txt` file)

  &emsp;4. Optionally, if you have it enabled, open `analysis.txt` and see the statistical analysis of `output.txt`. Same for seeing the attempted translation in `translated.txt`.

### How it works:
`v101_cleaned.txt` → `mapping.txt` → `output_numbers.txt` → `output.txt` → `analysis.txt` and `translated.txt`

## FAQ:

**Q: What is v101?**  
A: v101 is one of the standard transcription systems for representing Voynich Manuscript characters in a text format.

**Q: Is this a translation tool?**  
A: No. This is a transliteration tool, not a translation engine. It remaps the Voynich Manuscript characters into user-defined characters or strings.

**Q: Can one Voynich character map to multiple input and/or output characters?**<br>
A: Yes. The tool supports both multi-character input and output (e.g. `54=9~con`, `55=am~d`, and `55=4o~to` all work.)

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
A: If enabled, the analysis tools will calculate the character frequency and character entropy in `output.txt` as well as finding common prefixes, suffixes, and roots. Then everything is saved to `analysis.txt`.

**Q: Can I change the delimiters and symbol configuration?**<br>
A: Yes. At the top of `main.py` you can change the delimiters and symbols. Although it is recommended to keep the defaults as they are tested and compatible with the v101 transcription. You can also change the space and ambiguous space characters at the top of `main.py`.

**Q: Does it support languages other than English?**<br>
A: Yes. You can map the output to *any* characters or symbols supported by `.txt` and `.py` files, including other languages and custom alphabets.

## Planned Features:

These features are being considered for future versions of TVTT:

- Batch processing of multiple texts
- Morphological decomposition tools
- Dictionary assisted mapping suggestions (maybe even NLP & ML at some point)
- Option to use the EVA (or an alternative) transcription instead of the v101 transcription

Suggestions for new features are welcome — feel free to open an issue.

## Feedback & Ideas:
Thanks for checking this tool out! If you have a feature request, improvement idea, or find a bug, feel free to open an issue. This project is still a work in progress, and all suggestions are welcome.

## Credits & Citations:
&emsp;1. Voynich.nu for the copy of the v101 transcription. (https://voynich.nu/data/voyn_101.txt)<br>
&emsp;2. ChatGPT for assistance with the word part analysis in `main.py` and some bugs in the code as well as some of the documentation. (https://chatgpt.com/)<br>
&emsp;3. Google Gemini for the `cleaner.py` script and some bug fixes. (https://gemini.google.com/)
&emsp;4. The deep-translator Python library for the translation tool. (https://pypi.org/project/deep-translator/)
