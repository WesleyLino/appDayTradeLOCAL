import sys


def fix_indentation(filepath, start_line, end_line, dedent_spaces=4):
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    for i, line in enumerate(lines):
        # Line numbers are 1-indexed for the user, but 0-indexed here
        if start_line - 1 <= i <= end_line - 1:
            if line.startswith(" " * dedent_spaces):
                new_lines.append(line[dedent_spaces:])
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


if __name__ == "__main__":
    fix_indentation(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
