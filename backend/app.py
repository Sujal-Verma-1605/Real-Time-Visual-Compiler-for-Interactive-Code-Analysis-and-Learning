from flask import Flask, request, jsonify
from flask_cors import CORS
import re

app = Flask(__name__)
CORS(app)

# ---------------- LEXICAL ----------------
def tokenize(code):
    return re.findall(r'#include|<stdio.h>|printf|scanf|\w+|[{}();=,+\-*/&"]', code)

# ---------------- SYNTAX ----------------
def syntax_check(code):

    # check main
    if "main" not in code:
        return "Error: main() function missing"

    # check header
    if "#include<stdio.h>" not in code:
        return "Error: Missing #include<stdio.h>"

    # check braces
    stack = []
    for ch in code:
        if ch == '{': stack.append(ch)
        elif ch == '}':
            if not stack:
                return "Error: Unmatched }"
            stack.pop()

    if stack:
        return "Error: Missing }"

    # check semicolon
    lines = code.split("\n")
    for i, line in enumerate(lines):
        line = line.strip()

        if line.startswith("#include"):
            continue

        if line and not line.endswith(";") and not line.endswith("{") and not line.endswith("}"):
            return f"Error: Missing ; at line {i+1}"

    return None

# ---------------- SEMANTIC ----------------
def semantic_check(code):

    if "printf" in code and '"' not in code:
        return "Error: printf missing string"

    if "scanf" in code and "&" not in code:
        return "Error: scanf missing &"

    return "No Semantic Error"

# ---------------- INTERMEDIATE ----------------
def generate_icg(code):
    icg = []
    if "+" in code:
        icg.append("t1 = a + b")
        icg.append("a = t1")
    return "\n".join(icg) if icg else "No ICG"

# ---------------- MAIN ----------------
@app.route("/compile", methods=["POST"])
def compile():
    data = request.json
    code = data["code"]

    error = syntax_check(code)
    if error:
        return jsonify({"error": error})

    tokens = tokenize(code)

    tree = "Program\n"
    for t in tokens:
        tree += " ├─ " + t + "\n"

    semantic = semantic_check(code)
    icg = generate_icg(code)

    return jsonify({
        "tokens": tokens,
        "tree": tree,
        "semantic": semantic,
        "icg": icg,
        "opt": icg,
        "final": "Machine Code (simulated)"
    })

if __name__ == "__main__":
    app.run(debug=True)