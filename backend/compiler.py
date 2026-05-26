import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, jsonify, request
from flask_cors import CORS


app = Flask(__name__)
CORS(app)


SINGLE_CHAR_TOKENS = {
    ";": "SEMICOLON",
    "(": "LPAREN",
    ")": "RPAREN",
    "{": "LBRACE",
    "}": "RBRACE",
}


@dataclass
class Token:
    type: str
    value: str
    line: int
    column: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "value": self.value,
            "line": self.line,
            "column": self.column,
        }


class Lexer:
    token_pattern = re.compile(
        r"(?P<WHITESPACE>[ \t]+)|"
        r"(?P<NEWLINE>\n)|"
        r"(?P<COMMENT>//[^\n]*)|"
        r"(?P<KEYWORD>\b(?:int|if|else|while|for|return)\b)|"
        r"(?P<REL_OP>(?:==|!=|<=|>=|<|>))|"
        r"(?P<NUMBER>\b\d+\b)|"
        r"(?P<IDENTIFIER>\b[a-zA-Z_]\w*\b)|"
        r"(?P<ASSIGN>=)|"
        r"(?P<ARITH>[+\-*/])|"
        r"(?P<DELIM>[;(){}])|"
        r"(?P<MISMATCH>.)"
    )

    def tokenize(self, source: str) -> Tuple[List[Token], List[str]]:
        tokens: List[Token] = []
        lexical_errors: List[str] = []
        line = 1
        line_start = 0

        for match in self.token_pattern.finditer(source):
            kind = match.lastgroup
            value = match.group()
            column = match.start() - line_start + 1

            if kind in {"WHITESPACE", "COMMENT"}:
                continue
            if kind == "NEWLINE":
                line += 1
                line_start = match.end()
                continue
            if kind == "MISMATCH":
                lexical_errors.append(
                    f"Unexpected character '{value}' at line {line}, column {column}"
                )
                continue
            if kind == "DELIM":
                tokens.append(Token(SINGLE_CHAR_TOKENS[value], value, line, column))
                continue
            if kind == "KEYWORD":
                tokens.append(Token("KEYWORD", value, line, column))
                continue
            if kind == "IDENTIFIER":
                tokens.append(Token("IDENTIFIER", value, line, column))
                continue
            if kind == "NUMBER":
                tokens.append(Token("NUMBER", value, line, column))
                continue
            if kind == "ASSIGN":
                tokens.append(Token("ASSIGN", value, line, column))
                continue
            if kind == "ARITH":
                tokens.append(Token("ARITH_OP", value, line, column))
                continue
            if kind == "REL_OP":
                tokens.append(Token("REL_OP", value, line, column))
                continue

        tokens.append(Token("EOF", "", line, 1))
        return tokens, lexical_errors


class ParserError(Exception):
    pass


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.current = 0

    def parse(self) -> Dict[str, Any]:
        functions = []
        statements = []
        while not self._is_at_end():
            if self._is_function_decl():
                functions.append(self._function_declaration())
            else:
                statements.append(self._statement())
        return {"type": "Program", "functions": functions, "body": statements}

    def _is_function_decl(self) -> bool:
        if not self._check("KEYWORD", "int"):
            return False
        if self.current + 3 >= len(self.tokens):
            return False
        t1 = self.tokens[self.current + 1]
        t2 = self.tokens[self.current + 2]
        t3 = self.tokens[self.current + 3]
        return (
            t1.type == "IDENTIFIER"
            and t2.type == "LPAREN"
            and t3.type == "RPAREN"
        )

    def _function_declaration(self) -> Dict[str, Any]:
        self._consume("KEYWORD", "Expected function return type.", expected_value="int")
        name = self._consume("IDENTIFIER", "Expected function name.")
        self._consume("LPAREN", "Expected '(' after function name.")
        self._consume("RPAREN", "Expected ')' after function parameters.")
        body = self._block_statement()
        return {
            "type": "FunctionDecl",
            "return_type": "int",
            "name": name.value,
            "body": body,
            "line": name.line,
        }

    def _statement(self) -> Dict[str, Any]:
        if self._check("KEYWORD", "int"):
            self._advance()
            return self._declaration_statement()
        if self._match("KEYWORD", "if"):
            return self._if_statement()
        if self._match("KEYWORD", "while"):
            return self._while_statement()
        if self._match("KEYWORD", "for"):
            return self._for_statement()
        if self._match("KEYWORD", "return"):
            return self._return_statement()
        if self._match("LBRACE"):
            return self._block_body()
        if self._check("IDENTIFIER"):
            return self._assignment_statement()
        token = self._peek()
        raise ParserError(
            f"Unexpected token '{token.value}' at line {token.line}, column {token.column}"
        )

    def _block_statement(self) -> Dict[str, Any]:
        self._consume("LBRACE", "Expected '{' to start block.")
        return self._block_body()

    def _block_body(self) -> Dict[str, Any]:
        statements = []
        while not self._check("RBRACE") and not self._is_at_end():
            statements.append(self._statement())
        self._consume("RBRACE", "Expected '}' after block.")
        return {"type": "BlockStmt", "statements": statements}

    def _declaration_statement(self) -> Dict[str, Any]:
        identifier = self._consume("IDENTIFIER", "Expected identifier after type keyword.")
        initializer: Optional[Dict[str, Any]] = None
        if self._match("ASSIGN"):
            initializer = self._expression()
        self._consume("SEMICOLON", "Expected ';' after declaration.")
        return {
            "type": "VarDecl",
            "var_type": "int",
            "identifier": identifier.value,
            "initializer": initializer,
            "line": identifier.line,
        }

    def _assignment_statement(self) -> Dict[str, Any]:
        assignment = self._assignment_core()
        self._consume("SEMICOLON", "Expected ';' after assignment.")
        return assignment

    def _assignment_core(self) -> Dict[str, Any]:
        identifier = self._consume("IDENTIFIER", "Expected identifier.")
        self._consume("ASSIGN", "Expected '=' in assignment.")
        expression = self._expression()
        return {
            "type": "Assign",
            "identifier": identifier.value,
            "expression": expression,
            "line": identifier.line,
        }

    def _if_statement(self) -> Dict[str, Any]:
        self._consume("LPAREN", "Expected '(' after if.")
        condition = self._condition()
        self._consume("RPAREN", "Expected ')' after if condition.")
        then_branch = self._statement()
        else_branch = None
        if self._match("KEYWORD", "else"):
            else_branch = self._statement()
        return {
            "type": "IfStmt",
            "condition": condition,
            "then_branch": then_branch,
            "else_branch": else_branch,
        }

    def _while_statement(self) -> Dict[str, Any]:
        self._consume("LPAREN", "Expected '(' after while.")
        condition = self._condition()
        self._consume("RPAREN", "Expected ')' after while condition.")
        body = self._statement()
        return {"type": "WhileStmt", "condition": condition, "body": body}

    def _for_statement(self) -> Dict[str, Any]:
        self._consume("LPAREN", "Expected '(' after for.")
        initializer = None
        if not self._check("SEMICOLON"):
            if self._check("KEYWORD", "int"):
                self._advance()
                initializer = self._declaration_statement()
            else:
                initializer = self._assignment_statement()
        else:
            self._consume("SEMICOLON", "Expected ';' after for initializer.")

        condition = None
        if not self._check("SEMICOLON"):
            condition = self._condition()
        self._consume("SEMICOLON", "Expected ';' after for condition.")

        update = None
        if not self._check("RPAREN"):
            update = self._assignment_core()
        self._consume("RPAREN", "Expected ')' after for clauses.")
        body = self._statement()
        return {
            "type": "ForStmt",
            "initializer": initializer,
            "condition": condition,
            "update": update,
            "body": body,
        }

    def _return_statement(self) -> Dict[str, Any]:
        value = None
        if not self._check("SEMICOLON"):
            value = self._expression()
        self._consume("SEMICOLON", "Expected ';' after return.")
        return {"type": "ReturnStmt", "value": value}

    def _condition(self) -> Dict[str, Any]:
        left = self._expression()
        if self._match("REL_OP"):
            operator = self._previous().value
            right = self._expression()
            return {
                "type": "BinaryExpr",
                "operator": operator,
                "left": left,
                "right": right,
            }
        return left

    def _expression(self) -> Dict[str, Any]:
        return self._addition()

    def _addition(self) -> Dict[str, Any]:
        expr = self._multiplication()
        while self._match("ARITH_OP", "+") or self._match("ARITH_OP", "-"):
            operator = self._previous().value
            right = self._multiplication()
            expr = {
                "type": "BinaryExpr",
                "operator": operator,
                "left": expr,
                "right": right,
            }
        return expr

    def _multiplication(self) -> Dict[str, Any]:
        expr = self._primary()
        while self._match("ARITH_OP", "*") or self._match("ARITH_OP", "/"):
            operator = self._previous().value
            right = self._primary()
            expr = {
                "type": "BinaryExpr",
                "operator": operator,
                "left": expr,
                "right": right,
            }
        return expr

    def _primary(self) -> Dict[str, Any]:
        if self._match("NUMBER"):
            return {"type": "NumberLiteral", "value": int(self._previous().value)}
        if self._match("IDENTIFIER"):
            return {"type": "Identifier", "name": self._previous().value}
        if self._match("LPAREN"):
            expr = self._condition()
            self._consume("RPAREN", "Expected ')' after expression.")
            return expr
        token = self._peek()
        raise ParserError(
            f"Expected expression but found '{token.value}' at line {token.line}, column {token.column}"
        )

    def _match(self, token_type: str, value: Optional[str] = None) -> bool:
        if self._check(token_type, value):
            self._advance()
            return True
        return False

    def _check(self, token_type: str, value: Optional[str] = None) -> bool:
        if self._is_at_end():
            return False
        token = self._peek()
        if token.type != token_type:
            return False
        if value is not None and token.value != value:
            return False
        return True

    def _consume(
        self, token_type: str, message: str, expected_value: Optional[str] = None
    ) -> Token:
        if self._check(token_type, expected_value):
            return self._advance()
        token = self._peek()
        raise ParserError(f"{message} Found '{token.value}' at line {token.line}.")

    def _advance(self) -> Token:
        if not self._is_at_end():
            self.current += 1
        return self._previous()

    def _is_at_end(self) -> bool:
        return self._peek().type == "EOF"

    def _peek(self) -> Token:
        return self.tokens[self.current]

    def _previous(self) -> Token:
        return self.tokens[self.current - 1]


class SemanticAnalyzer:
    def __init__(self):
        self.scopes: List[Dict[str, Dict[str, Any]]] = [dict()]
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def analyze(self, program: Dict[str, Any]) -> Dict[str, Any]:
        for statement in program.get("body", []):
            self._analyze_statement(statement)
        for function in program.get("functions", []):
            self._push_scope()
            self._analyze_statement(function["body"])
            self._pop_scope()

        table_view = []
        for scope in self.scopes:
            for name, data in scope.items():
                table_view.append(
                    {
                        "name": name,
                        "type": data["type"],
                        "initialized": data["initialized"],
                    }
                )
        return {"errors": self.errors, "warnings": self.warnings, "symbol_table": table_view}

    def _analyze_statement(self, node: Dict[str, Any]) -> None:
        node_type = node["type"]
        if node_type == "VarDecl":
            self._handle_declaration(node)
            return
        if node_type == "Assign":
            self._handle_assignment(node)
            return
        if node_type == "BlockStmt":
            self._push_scope()
            for child in node["statements"]:
                self._analyze_statement(child)
            self._pop_scope()
            return
        if node_type == "IfStmt":
            self._evaluate_expression_type(node["condition"])
            self._analyze_statement(node["then_branch"])
            if node["else_branch"] is not None:
                self._analyze_statement(node["else_branch"])
            return
        if node_type == "WhileStmt":
            self._evaluate_expression_type(node["condition"])
            self._analyze_statement(node["body"])
            return
        if node_type == "ForStmt":
            self._push_scope()
            if node["initializer"] is not None:
                self._analyze_statement(node["initializer"])
            if node["condition"] is not None:
                cond_type = self._evaluate_expression_type(node["condition"])
                if cond_type not in {"bool", "int"}:
                    self.errors.append("Invalid for-loop condition type.")
            else:
                self.warnings.append(
                    "For-loop has no condition; it may run forever unless broken inside the loop body."
                )
            if node["update"] is not None:
                self._analyze_statement(node["update"])
            elif node["condition"] is not None and self._is_truthy_constant(node["condition"]):
                self.warnings.append(
                    "For-loop condition is always true and has no update clause; possible infinite loop."
                )
            self._analyze_statement(node["body"])
            self._pop_scope()
            return
        if node_type == "ReturnStmt":
            if node["value"] is not None:
                return_type = self._evaluate_expression_type(node["value"])
                if return_type != "int":
                    self.errors.append("Return type mismatch: expected int.")
            return

    def _handle_declaration(self, node: Dict[str, Any]) -> None:
        name = node["identifier"]
        current_scope = self.scopes[-1]
        if name in current_scope:
            self.errors.append(f"Duplicate declaration of variable '{name}'.")
            return
        initialized = node["initializer"] is not None
        current_scope[name] = {"type": "int", "initialized": initialized}
        if node["initializer"] is not None:
            expr_type = self._evaluate_expression_type(node["initializer"])
            if expr_type not in {"int", "bool"}:
                self.errors.append(f"Type mismatch when initializing '{name}'.")

    def _handle_assignment(self, node: Dict[str, Any]) -> None:
        name = node["identifier"]
        symbol = self._resolve_symbol(name)
        if symbol is None:
            self.errors.append(f"Assignment to undeclared variable '{name}'.")
            return
        expr_type = self._evaluate_expression_type(node["expression"])
        if expr_type != "int":
            self.errors.append(f"Type mismatch in assignment to '{name}'.")
            return
        symbol["initialized"] = True

    def _evaluate_expression_type(self, expr: Dict[str, Any]) -> str:
        expr_type = expr["type"]
        if expr_type == "NumberLiteral":
            return "int"
        if expr_type == "Identifier":
            name = expr["name"]
            symbol = self._resolve_symbol(name)
            if symbol is None:
                self.errors.append(f"Use of undeclared variable '{name}'.")
                return "unknown"
            return symbol["type"]
        if expr_type == "BinaryExpr":
            operator = expr["operator"]
            left = self._evaluate_expression_type(expr["left"])
            right = self._evaluate_expression_type(expr["right"])
            if operator in {"+", "-", "*", "/"}:
                if left != "int" or right != "int":
                    return "unknown"
                return "int"
            if operator in {"<", ">", "<=", ">=", "==", "!="}:
                if left != "int" or right != "int":
                    return "unknown"
                return "bool"
        return "unknown"

    def _is_truthy_constant(self, expr: Dict[str, Any]) -> bool:
        if expr["type"] == "NumberLiteral":
            return expr["value"] != 0
        return False

    def _resolve_symbol(self, name: str) -> Optional[Dict[str, Any]]:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def _push_scope(self) -> None:
        self.scopes.append(dict())

    def _pop_scope(self) -> None:
        if len(self.scopes) > 1:
            self.scopes.pop()


class TACGenerator:
    def __init__(self):
        self.temp_counter = 0
        self.label_counter = 0
        self.code: List[str] = []

    def generate(self, program: Dict[str, Any]) -> List[str]:
        for statement in program.get("body", []):
            self._emit_statement(statement)
        for function in program.get("functions", []):
            self.code.append(f"LABEL FUNC_{function['name']}")
            self._emit_statement(function["body"])
            self.code.append("END_FUNC")
        return self.code

    def _emit_statement(self, statement: Dict[str, Any]) -> None:
        node_type = statement["type"]
        if node_type == "VarDecl":
            if statement["initializer"] is not None:
                source = self._emit_expression(statement["initializer"])
                self.code.append(f"{statement['identifier']} = {source}")
            return
        if node_type == "Assign":
            source = self._emit_expression(statement["expression"])
            self.code.append(f"{statement['identifier']} = {source}")
            return
        if node_type == "BlockStmt":
            for child in statement["statements"]:
                self._emit_statement(child)
            return
        if node_type == "IfStmt":
            else_label = self._next_label("ELSE")
            end_label = self._next_label("ENDIF")
            condition = self._emit_expression(statement["condition"])
            self.code.append(f"IF_FALSE {condition} GOTO {else_label}")
            self._emit_statement(statement["then_branch"])
            self.code.append(f"GOTO {end_label}")
            self.code.append(f"LABEL {else_label}")
            if statement["else_branch"] is not None:
                self._emit_statement(statement["else_branch"])
            self.code.append(f"LABEL {end_label}")
            return
        if node_type == "WhileStmt":
            start_label = self._next_label("WHILE_START")
            end_label = self._next_label("WHILE_END")
            self.code.append(f"LABEL {start_label}")
            condition = self._emit_expression(statement["condition"])
            self.code.append(f"IF_FALSE {condition} GOTO {end_label}")
            self._emit_statement(statement["body"])
            self.code.append(f"GOTO {start_label}")
            self.code.append(f"LABEL {end_label}")
            return
        if node_type == "ForStmt":
            if statement["initializer"] is not None:
                self._emit_statement(statement["initializer"])
            start_label = self._next_label("FOR_START")
            end_label = self._next_label("FOR_END")
            self.code.append(f"LABEL {start_label}")
            if statement["condition"] is not None:
                condition = self._emit_expression(statement["condition"])
                self.code.append(f"IF_FALSE {condition} GOTO {end_label}")
            self._emit_statement(statement["body"])
            if statement["update"] is not None:
                self._emit_statement(statement["update"])
            self.code.append(f"GOTO {start_label}")
            self.code.append(f"LABEL {end_label}")
            return
        if node_type == "ReturnStmt":
            if statement["value"] is None:
                self.code.append("RETURN")
            else:
                value = self._emit_expression(statement["value"])
                self.code.append(f"RETURN {value}")

    def _emit_expression(self, expr: Dict[str, Any]) -> str:
        expr_type = expr["type"]
        if expr_type == "NumberLiteral":
            return str(expr["value"])
        if expr_type == "Identifier":
            return expr["name"]
        if expr_type == "BinaryExpr":
            left = self._emit_expression(expr["left"])
            right = self._emit_expression(expr["right"])
            temp = self._next_temp()
            self.code.append(f"{temp} = {left} {expr['operator']} {right}")
            return temp
        return "0"

    def _next_temp(self) -> str:
        self.temp_counter += 1
        return f"t{self.temp_counter}"

    def _next_label(self, prefix: str) -> str:
        self.label_counter += 1
        return f"{prefix}_{self.label_counter}"


class Optimizer:
    assignment_pattern = re.compile(r"^(\w+)\s*=\s*(.+)$")
    binary_pattern = re.compile(r"^(\w+|\d+)\s*([+\-*/])\s*(\w+|\d+)$")

    def optimize(self, tac_code: List[str]) -> Dict[str, List[str]]:
        before = list(tac_code)
        transformed: List[str] = []
        used_variables = self._find_used_variables(tac_code)

        for instruction in tac_code:
            parsed = self._parse_assignment(instruction)
            if parsed is None:
                transformed.append(instruction)
                continue

            target, expression = parsed
            folded = self._try_constant_fold(target, expression)
            final_instruction = folded if folded is not None else instruction

            if (
                target.startswith("t")
                and target not in used_variables
                and self._is_pure_assignment(final_instruction)
            ):
                continue
            transformed.append(final_instruction)

        return {"before": before, "after": transformed}

    def _find_used_variables(self, tac_code: List[str]) -> set:
        used = set()
        for line in tac_code:
            names = re.findall(r"\b[a-zA-Z_]\w*\b", line)
            if line.startswith("LABEL "):
                names = names[1:]
            if line.startswith("GOTO "):
                names = []
            if line.startswith("IF_FALSE "):
                # Format: IF_FALSE <cond> GOTO <label>
                parts = line.split()
                if len(parts) >= 2:
                    used.add(parts[1])
                continue
            if "=" in line:
                _, rhs = line.split("=", 1)
                rhs_names = re.findall(r"\b[a-zA-Z_]\w*\b", rhs)
                for name in rhs_names:
                    used.add(name)
            else:
                for name in names:
                    used.add(name)
        return used

    def _parse_assignment(self, line: str) -> Optional[Tuple[str, str]]:
        match = self.assignment_pattern.match(line.strip())
        if not match:
            return None
        return match.group(1), match.group(2).strip()

    def _is_pure_assignment(self, line: str) -> bool:
        return line.count("=") == 1 and not line.startswith(("IF_FALSE", "LABEL", "GOTO"))

    def _try_constant_fold(self, target: str, expression: str) -> Optional[str]:
        match = self.binary_pattern.match(expression)
        if not match:
            return None
        left, op, right = match.group(1), match.group(2), match.group(3)
        if not left.isdigit() or not right.isdigit():
            return None
        left_n = int(left)
        right_n = int(right)
        if op == "+":
            value = left_n + right_n
        elif op == "-":
            value = left_n - right_n
        elif op == "*":
            value = left_n * right_n
        elif op == "/":
            if right_n == 0:
                return None
            value = left_n // right_n
        else:
            return None
        return f"{target} = {value}"


class MachineCodeGenerator:
    binary_pattern = re.compile(
        r"^(\w+)\s*=\s*(\w+|\d+)\s*([+\-*/<>]|<=|>=|==|!=)\s*(\w+|\d+)$"
    )
    direct_assign_pattern = re.compile(r"^(\w+)\s*=\s*(\w+|\d+)$")
    if_false_pattern = re.compile(r"^IF_FALSE\s+(\w+)\s+GOTO\s+(\w+)$")
    goto_pattern = re.compile(r"^GOTO\s+(\w+)$")
    label_pattern = re.compile(r"^LABEL\s+(\w+)$")
    return_pattern = re.compile(r"^RETURN(?:\s+(\w+|\d+))?$")

    op_map = {
        "+": "ADD",
        "-": "SUB",
        "*": "MUL",
        "/": "DIV",
        "<": "CMP_LT",
        ">": "CMP_GT",
        "<=": "CMP_LE",
        ">=": "CMP_GE",
        "==": "CMP_EQ",
        "!=": "CMP_NE",
    }

    def generate(self, tac_code: List[str]) -> List[str]:
        machine_code: List[str] = []
        for instruction in tac_code:
            instruction = instruction.strip()
            if not instruction:
                continue
            if instruction == "END_FUNC":
                machine_code.append("RET")
                continue
            return_match = self.return_pattern.match(instruction)
            if return_match:
                return_value = return_match.group(1)
                if return_value is not None:
                    machine_code.append(f"LOAD {return_value}")
                machine_code.append("RET")
                continue
            label_match = self.label_pattern.match(instruction)
            if label_match:
                machine_code.append(f"{label_match.group(1)}:")
                continue
            goto_match = self.goto_pattern.match(instruction)
            if goto_match:
                machine_code.append(f"JMP {goto_match.group(1)}")
                continue
            if_false_match = self.if_false_pattern.match(instruction)
            if if_false_match:
                cond, label = if_false_match.groups()
                machine_code.extend([f"LOAD {cond}", f"JZ {label}"])
                continue
            binary_match = self.binary_pattern.match(instruction)
            if binary_match:
                target, left, operator, right = binary_match.groups()
                machine_code.extend(
                    [
                        f"LOAD {left}",
                        f"{self.op_map[operator]} {right}",
                        f"STORE {target}",
                    ]
                )
                continue
            assign_match = self.direct_assign_pattern.match(instruction)
            if assign_match:
                target, value = assign_match.groups()
                machine_code.extend([f"LOAD {value}", f"STORE {target}"])
                continue
            machine_code.append(f"; unsupported instruction: {instruction}")
        return machine_code


def compile_source(source: str) -> Dict[str, Any]:
    lexer = Lexer()
    tokens, lexical_errors = lexer.tokenize(source)
    token_list = [token.to_dict() for token in tokens if token.type != "EOF"]

    if lexical_errors:
        return {
            "tokens": token_list,
            "syntax": {"status": "invalid", "tree": {}, "errors": lexical_errors},
            "semantic": {"errors": [], "warnings": [], "symbol_table": []},
            "intermediate_code": [],
            "optimized_code": {"before": [], "after": []},
            "machine_code": [],
        }

    try:
        parser = Parser(tokens)
        parse_tree = parser.parse()
        syntax_status = "valid"
        syntax_errors: List[str] = []
    except ParserError as error:
        parse_tree = {}
        syntax_status = "invalid"
        syntax_errors = [str(error)]

    if syntax_status == "invalid":
        return {
            "tokens": token_list,
            "syntax": {"status": syntax_status, "tree": parse_tree, "errors": syntax_errors},
            "semantic": {"errors": [], "warnings": [], "symbol_table": []},
            "intermediate_code": [],
            "optimized_code": {"before": [], "after": []},
            "machine_code": [],
        }

    semantic = SemanticAnalyzer().analyze(parse_tree)
    tac = TACGenerator().generate(parse_tree)
    optimized = Optimizer().optimize(tac)
    machine = MachineCodeGenerator().generate(optimized["after"])

    return {
        "tokens": token_list,
        "syntax": {"status": syntax_status, "tree": parse_tree, "errors": syntax_errors},
        "semantic": semantic,
        "intermediate_code": tac,
        "optimized_code": optimized,
        "machine_code": machine,
    }


@app.route("/compile", methods=["POST"])
def compile_endpoint():
    payload = request.get_json(silent=True) or {}
    source_code = payload.get("source_code", "")
    if not isinstance(source_code, str):
        return jsonify({"error": "source_code must be a string"}), 400
    result = compile_source(source_code)
    return jsonify(result), 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)
