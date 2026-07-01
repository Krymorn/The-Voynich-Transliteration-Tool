# The Voynich Transliteration Tool (TVTT)
**Version 1.8.0**

Create your own Voynich Manuscript transliteration based on the v101/EVA transcriptions.

## Overview
TVTT is a cryptographic workbench that replaces each character in the v101/EVA transcriptions of the Voynich Manuscript with a customizable, user-defined mapping. 

Beyond simple transliteration, the tool acts as a testing ground for decipherment theories. It has the capability to perform **deep statistical analysis**—including Zipf's Law, Entropy calculation, Sukhotin's vowel detection, and more—to determine if your mapping behaves like a natural language or random noise. It also supports **Dialect Sectioning**, allowing you to isolate and test specific "languages" (e.g. Currier A vs. B) within the manuscript.

## Features
- **Configuration File**: Configuration file for easy access to settings. Follows basic Json formatting and syntax.
- **Positional Context Mapping:** Distinct rules for characters at the start (`@`), end (`/`), or middle of words.
- **Occurrence Mapping:** Specific rules for the 1st, 2nd, 3rd, or 4th time a character appears in a word (using `'`, `"`, `:`, `;`).
- **Multi-character Mapping:** Map one input character to many (e.g., `{"f": "abc",}`) or many input characters to one (e.g., `{"fa1": "d"},`).
- **Dialect Sectioning:** Restrict processing to specific line ranges to isolate "Currier A" (Herbal) or "Currier B" (Biological) dialects. (Note: Currier A ends on v101 line 1507 and line 2673 in EVA2).
- **Corpus Analysis ("The Combinator"):** A post-processing engine that compares your output against real dictionaries.
  - **Fuzzy Matching:** Corrects "typos" using Dynamic Strictness (strict for short words, looser for long words) (Note: Scales from 1 to 3, 1 being the most tolerant and 3 the least. Recommended to keep strictness at the default of 2).
  - **Word Merging:** Detects and fixes segmentation errors (e.g., merging "in" + "to" -> "into").
- **Translation Module:** Attempt to automatically translate your output into English (via Google Translate) to check for intelligible sentences.
- **Deep Statistical Analysis:**
  - **Entropy Calculation:** Measures the randomness of your output.
  - **Sukhotin Vowel Analysis:** Algorithmically predicts vowels based on character adjacency.
  - **Reduplication Detection:** Verifies if your mapping preserves the manuscript's frequent word repetition (e.g., *chol chol*).
  - **Zipf's Law Visualization:** Generates a log-log plot to compare your text's frequency distribution against natural language laws.
- **HTML Comparison Report:** Generates a side-by-side visual report (`comparison.html`) of the original text vs. your transliteration.

## Tutorial

### File Structure
- `cleaner.py`: Cleans the raw `v101.txt` and saves it to `v101_cleaned.txt`/`eva_cleaned.txt`. Recommended to leave as it is and use already generated cleaned files.
- `mapping.py`: Scans the cleaned text to auto-populate either `v101_mapping.json` or`eva_mapping.json` with all unique characters found (including the v101 extended character set). Again recommended to leave as is and use already generated files.
- `v101_mapping.json`/`eva_mapping.json`: The core configuration files where you define your substitution rules.
- `main.py`: Reads `v101_mapping.json`/`eva_mapping.json`, processes the text, and generates all outputs.
- `reference_texts/`: The folder where you place `.txt` dictionaries (e.g. `latin.txt`) for the fuzzy matcher to use. Name of file is auto-detected and does not need to be standardized (Both latin.txt and latin_dictionary.txt will work).
- `output.txt`: The final transliterated text (uses underscores `_` for spaces and hyphens `-` for ambigous spaces by default, this is changeable in settings).
- `output_fuzzy.txt`: The transliterated text **after** being auto-corrected and merged by the Corpus Analysis.
- `discovery_report.txt`: A report listing every word merge and typo correction found by the system.
- `analysis.txt`: Statistical data (Frequency, Entropy, Affixes, Vowel predictions, Reduplication).
- `zipf_analysis.png`: A graph visualizing word frequency using Zipf's Law.
- `comparison.html`: A visual report comparing source vs. output line-by-line. Can be configured to either be in plaintext or use the basic v101 font (No support for EVA2 yet).
- `translated.txt`: (Optional) The machine-translated version of your output using the deep_translate library (Specifically Google Translate). Use the translationLanguage configuration to set the language (Use the enablePrintLanguages config to have your options listed in terminal).

**NOTE:** Do not edit `v101.txt`/`eva.txt` or `v101_cleaned.txt`/`eva_cleaned.txt` manually unless you absolutely know what you are doing. Transcriptions were downloaded from https://voynich.nu/transcr.html.

### Syntax for `v101_mapping.txt`/`eva_mapping.txt`
- **`@`** — End of line: Use this mapping only if the character is at the **start** of a word (e.g., `{"f": "a@"}`).
- **`/`** — End of line: Use this mapping only if the character is at the **end** of a word (e.g., `{"9": "b/"}`).
- **`'`**, **`"`**, **`:`**, **`;`** — Use these for the 1st, 2nd, 3rd, and 4th **occurrence** of a character within a single word. Same formatting as `@` and `/`.
- **No Symbol** — Provided mapping will be used in any position if no positional rule is specified.

**NOTE:** `{` and `}` must only be at the beginning and end of the `.json` files for the Json interpreter library to parse the file correctly.

**NOTE 2:** Priority order applies. `@` and `/` are prioritized before a mapping of the same input character(s) when no positional rule is specified.

### Instructions
1.  **Install:** Download the source code (the `.zip` file) from the latest release. Ensure you have Python installed (Preferably the latest version).
2. **Dependencies:** Install dependencies using the following command: `pip install matplotlib deep-translator numpy`
    
2.  **Configure:** Open `config.json` to adjust settings:
    * Optional: Set `startLine` and `endLine` to test specific sections (e.g., 0-1413 for the v101 Herbal Section of the manuscript) or leave `endLine` as `None` to continue until the end of the input file.
    * Toggle `enableFuzzyMatching` to `True` if you want to use the fuzzy matcher. Adjust `toleranceLevel` (1-3) to control strictness (1 = lenient, 3 = strict).
    * Toggle `enableHTMLComparison` and/or `enableZipfsLawGeneration` as needed.
    * Set `enableTranslation = True` to attempt Google Translate. Change `translationLanguage` to your desired target (e.g., `'en'` for English, `'la' for Latin`).
    
3.  **Setup References:** If using Corpus Analysis, find a text file of a dictionary (e.g. `latin.txt`) and place it inside the `reference_texts` folder.

4.  **Map:** Edit `v101_mapping.json`/`eva_mapping.json` to define your substitution cipher.

5.  **Run:** Execute `main.py`. (Run `python main.py` in Terminal/Command Line)

6.  **Analyze:** Review `output.txt`, `output_fuzzy.txt`, `analysis.txt`, `zipf_analysis.png`, and `comparison.html`.

## Troubleshooting & FAQ

#### **CRITICAL: "Why does `comparison.html` look unchanged?"**
**Browser Caching Issue:** If you run the script and `comparison.html` still shows your old results (or the original text), your web browser is likely loading a cached version of the file.
* **Fix:** With the HTML file open in your browser, perform a **Hard Refresh** by pressing `Ctrl + F5` (Windows) or `Cmd + Shift + R` (Mac). This forces the browser to reload the actual file from the disk.

**Q: Can I map multiple input characters to a single letter?**
A: Yes. The tool supports multi-character inputs (n-graphs).
* *Example:* `105=4o~d@` (This tells the tool to treat every instance of the sequence "4o" as the letter "d").
* The tool prioritizes the longest matches first, so if you have mappings for both `4` and `4o`, it will correctly identify `4o` as a single unit and replace it before falling back to `4`.

**Q: Can I map one Voynich character to multiple letters?**
A: Yes.
* *Example:* `53=9~con` (This maps the single symbol `9` to the string `con`).

**Q: What are Currier A and Currier B?**
A: These are the two distinct "languages" or "hands" in the manuscript. You can use the `startLine` and `endLine` variables in `main.py` to test your mapping on just one section at a time (e.g., lines 1–1413 for v101 Herbal section of the manuscript).

**Q: Why is "Reduplication" analysis included?**
A: The Voynich manuscript features frequent immediate repetition (e.g., *chol chol*). If your mapping turns this into something unnatural like *the the*, it may be incorrect. This feature helps verify if your mapping preserves this structural feature.

**Q: What does the Zipf's Law graph show?**
A: Natural languages follow a specific slope where the most common word is twice as frequent as the second, etc. If the "Ideal" line and your "Data" points are wildly different, your output may be gibberish rather than language.

**Q: Where can I get v101 and EVA transliteration references?**
A: [Voynich.nu](https://www.voynich.nu/transcr.html) has excellent reference charts and downloadable copies of many transcriptions.

## Planned Features
- Font support for EVA2

## Credits & Citations
1.  **Voynich.nu** for the v101 and EVA transcriptions (https://voynich.nu/data/voyn_101.txt and https://voynich.nu/data/ZL3b-n.txt).<br>
2.  **Voynichese.com** for reference while testing.
2.  **ChatGPT** for assistance with word part analysis logic.<br>
3.  **Google Gemini** for `cleaner.py`, statistical algorithms (Sukhotin/Zipf), and structural improvements.<br>
4.  **deep-translator** Python library for the translation module.<br>
