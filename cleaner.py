import re
import argparse
import sys


def clean_transcription(text):
    """
    - Removes anything between < and >, { and }, and [ and ]
    - Removes - and = characters
    """

    # Remove everything between < and >
    text = re.sub(r"<[^>]*>", "", text)

    # Remove everything between { and } (Fixed regex)
    text = re.sub(r"\{[^}]*\}", "", text)

    # Remove everything between [ and ] (Fixed regex)
    text = re.sub(r"\[[^\]]*\]", "", text)

    # Remove - and = characters which typically mark the end of a line in the transcription
    text = text.replace("=", "")
    text = text.replace("-", "")

    return text


def process_file(input_path, output_path):
    try:
        with open(input_path, "r", encoding="utf-8") as file:
            raw_text = ""
            for line in file.readlines():
                if not line.startswith("#"): 
                    raw_text = raw_text + line
            raw_text = raw_text.replace(" ", "")
    except FileNotFoundError:
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR reading file: {e}")
        sys.exit(1)

    cleaned_text = clean_transcription(raw_text)

    try:
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(cleaned_text)

        print(f"Input : {input_path}")
        print(f"Output: {output_path}\n")

    except Exception as e:
        print(f"ERROR writing file: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Clean Voynich transcription by removing metadata brackets and line markers."
    )

    parser.add_argument("input_file", help="Input file (example: v101.txt)")
    parser.add_argument("output_file", help="Output file (example: v101_cleaned.txt)")

    args = parser.parse_args()

    process_file(args.input_file, args.output_file)

# Run main
if __name__ == "__main__":
    main()