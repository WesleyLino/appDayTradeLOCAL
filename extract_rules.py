def extract_text(pdf_path):
    text = ""
    try:
        import pypdf

        print("Using pypdf...")
        reader = pypdf.PdfReader(pdf_path)
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except ImportError:
        pass

    try:
        import PyPDF2

        print("Using PyPDF2...")
        reader = PyPDF2.PdfReader(pdf_path)
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except ImportError:
        pass

    try:
        from pdfminer.high_level import extract_text

        print("Using pdfminer...")
        text = extract_text(pdf_path)
        return text
    except ImportError:
        pass

    return None


if __name__ == "__main__":
    pdf_path = "Regras e parametros de negociacao.pdf"
    content = extract_text(pdf_path)

    if content:
        with open("rules_utf8.txt", "w", encoding="utf-8") as f:
            f.write(content)
        print("Successfully wrote content to rules_utf8.txt")
    else:
        print(
            "ERROR: No suitable PDF library found. Please install pypdf with: pip install pypdf"
        )
