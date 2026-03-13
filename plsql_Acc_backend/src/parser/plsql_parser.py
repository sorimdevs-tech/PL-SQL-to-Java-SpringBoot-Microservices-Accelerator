"""
PL/SQL Parser using ANTLR
Parses PL/SQL code and generates Abstract Syntax Tree (AST)
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

# Add ANTLR generated parsers to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'antlr'))

try:
    from antlr4 import *
    from antlr4.error.ErrorListener import ErrorListener
    # Import generated ANTLR parsers (these will be generated later)
    from .generated.PlSqlLexer import PlSqlLexer
    from .generated.PlSqlParser import PlSqlParser
    from .generated.PlSqlListener import PlSqlListener
except ImportError:
    # Fallback if ANTLR parsers not generated yet
    PlSqlLexer = None
    PlSqlParser = None
    PlSqlListener = object
    ErrorListener = object
    InputStream = None
    CommonTokenStream = None
    ParseTreeWalker = None

from ..utils.logger import get_logger

logger = get_logger(__name__)


SQLPLUS_DIRECTIVE_PATTERN = re.compile(
    r"^\s*(?:set|spool|prompt|whenever|host|column|ttitle|btitle|define|undefine|accept|pause|"
    r"connect|conn|exit|quit)\b",
    flags=re.IGNORECASE,
)
OBJECT_DECL_PATTERN = re.compile(
    r"\bcreate\s+(?:or\s+replace\s+)?(procedure|function|trigger|package(?:\s+body)?)\s+([`\"\w$#\.]+)",
    flags=re.IGNORECASE,
)
PARAM_PATTERN = re.compile(
    r"""^\s*["`]?([\w$#]+)["`]?\s+(?:(in\s+out|in|out)\s+)?(.+?)\s*$""",
    flags=re.IGNORECASE,
)


def preprocess_plsql_for_parser(content: str) -> str:
    """Normalize SQL*Plus-heavy scripts so they are friendlier to ANTLR parsing."""
    if not content:
        return ""

    content = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    processed_lines: List[str] = []
    for line in content.split("\n"):
        stripped = line.strip()
        lowered = stripped.lower()

        # SQL*Plus line comments and scripting commands are not valid PL/SQL tokens.
        if lowered.startswith("rem ") or lowered == "rem":
            continue
        if SQLPLUS_DIRECTIVE_PATTERN.match(stripped):
            continue
        if stripped in {"/", "@@", "@"}:
            continue
        if stripped.startswith("@@") or stripped.startswith("@"):
            continue

        processed_lines.append(line)

    cleaned = "\n".join(processed_lines)
    # Replace bind notation and declaration datatypes often used in Oracle scripts.
    cleaned = re.sub(r":(old|new)\.([A-Za-z_][\w$#]*)", r"\1_\2", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b[\w$#\.]+\s*%type\b", "NUMBER", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b[\w$#\.]+\s*%rowtype\b", "NUMBER", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"&([A-Za-z_][\w$#]*)", r"\1", cleaned)
    return cleaned


def _ctx_text(node, default: str = "") -> str:
    """Return context text, handling optional list-valued parser accessors."""
    if node is None:
        return default
    if isinstance(node, list):
        if not node:
            return default
        node = node[0]
    return node.getText() if hasattr(node, "getText") else default


class PLSQLParseError(Exception):
    """Custom exception for PL/SQL parsing errors"""
    pass


class PLSQLErrorListener(ErrorListener):
    """Custom error listener for PL/SQL parsing"""
    
    def __init__(self):
        self.errors = []
    
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        error_msg = f"Line {line}:{column} - {msg}"
        self.errors.append(error_msg)
        logger.error(f"PL/SQL parsing error: {error_msg}")


class PLSQLASTBuilder(PlSqlListener):
    """Builds AST from PL/SQL parse tree"""
    
    def __init__(self):
        self.ast = {
            'type': 'plsql_file',
            'procedures': [],
            'functions': [],
            'triggers': [],
            'packages': [],
            'declarations': [],
            'executables': [],
            'exceptions': []
        }
        self.current_object = None
        self.current_block = None
    
    def enterCreate_procedure_body(self, ctx: PlSqlParser.Create_procedure_bodyContext):
        """Handle procedure definition"""
        procedure_name = _ctx_text(ctx.procedure_name(), "anonymous_procedure")
        self.current_object = {
            'type': 'procedure',
            'name': procedure_name,
            'parameters': [],
            'variables': [],
            'statements': [],
            'exceptions': []
        }
        self.ast['procedures'].append(self.current_object)
    
    def enterCreate_function_body(self, ctx: PlSqlParser.Create_function_bodyContext):
        """Handle function definition"""
        function_name = _ctx_text(ctx.function_name(), "anonymous_function")
        self.current_object = {
            'type': 'function',
            'name': function_name,
            'parameters': [],
            'return_type': None,
            'variables': [],
            'statements': [],
            'exceptions': []
        }
        self.ast['functions'].append(self.current_object)
    
    def enterCreate_trigger(self, ctx: PlSqlParser.Create_triggerContext):
        """Handle trigger definition"""
        trigger_name = _ctx_text(ctx.trigger_name(), "anonymous_trigger")
        self.current_object = {
            'type': 'trigger',
            'name': trigger_name,
            'timing': None,
            'event': None,
            'table': None,
            'statements': []
        }
        self.ast['triggers'].append(self.current_object)
    
    def enterCreate_package(self, ctx: PlSqlParser.Create_packageContext):
        """Handle package definition"""
        package_name = _ctx_text(ctx.package_name(), "anonymous_package")
        self.current_object = {
            'type': 'package',
            'name': package_name,
            'procedures': [],
            'functions': [],
            'variables': [],
            'constants': [],
            'types': []
        }
        self.ast['packages'].append(self.current_object)
    
    def enterParameter(self, ctx: PlSqlParser.ParameterContext):
        """Handle parameter definition"""
        if self.current_object:
            param_name = _ctx_text(ctx.parameter_name(), "param")
            param_type = _ctx_text(ctx.datatype(), "UNKNOWN")
            param_mode = _ctx_text(ctx.parameter_mode(), 'IN')
            
            param = {
                'name': param_name,
                'type': param_type,
                'mode': param_mode
            }
            self.current_object['parameters'].append(param)
    
    def enterVariable_declaration(self, ctx: PlSqlParser.Variable_declarationContext):
        """Handle variable declaration"""
        if self.current_object:
            var_name = _ctx_text(ctx.variable_name(), "var")
            var_type = _ctx_text(ctx.datatype(), "UNKNOWN")
            
            var = {
                'name': var_name,
                'type': var_type
            }
            self.current_object['variables'].append(var)
    
    def enterSql_statement(self, ctx: PlSqlParser.Sql_statementContext):
        """Handle SQL statements"""
        if self.current_object:
            sql_text = ctx.getText()
            statement = {
                'type': 'sql_statement',
                'text': sql_text
            }
            self.current_object['statements'].append(statement)
    
    def enterIf_statement(self, ctx: PlSqlParser.If_statementContext):
        """Handle IF statements"""
        if self.current_object:
            condition = _ctx_text(ctx.condition(), None)
            statement = {
                'type': 'if_statement',
                'condition': condition,
                'then_statements': [],
                'else_statements': []
            }
            self.current_object['statements'].append(statement)
    
    def enterLoop_statement(self, ctx: PlSqlParser.Loop_statementContext):
        """Handle LOOP statements"""
        if self.current_object:
            loop_type = ctx.getChild(0).getText().upper()
            statement = {
                'type': 'loop_statement',
                'loop_type': loop_type,
                'statements': []
            }
            self.current_object['statements'].append(statement)
    
    def enterException_handler(self, ctx: PlSqlParser.Exception_handlerContext):
        """Handle exception blocks"""
        if self.current_object:
            exception_name = _ctx_text(ctx.exception_name(), 'OTHERS')
            exception_handler = {
                'exception': exception_name,
                'statements': []
            }
            self.current_object['exceptions'].append(exception_handler)


class PLSQLParser:
    """Main PL/SQL parser class"""
    
    def __init__(self):
        """Initialize PL/SQL parser"""
        if PlSqlLexer is None or PlSqlParser is None:
            logger.warning("ANTLR parsers not available. Install ANTLR or generate parsers first.")

    @staticmethod
    def _normalize_name(raw_name: str) -> str:
        """Normalize schema-qualified or quoted object names."""
        normalized = raw_name.strip().strip('"`')
        if "." in normalized:
            normalized = normalized.split(".")[-1]
        return normalized

    @staticmethod
    def _split_top_level_csv(content: str) -> List[str]:
        """Split comma-separated tokens while respecting nested parentheses."""
        parts: List[str] = []
        buffer: List[str] = []
        depth = 0
        for char in content:
            if char == "(":
                depth += 1
            elif char == ")" and depth > 0:
                depth -= 1
            elif char == "," and depth == 0:
                chunk = "".join(buffer).strip()
                if chunk:
                    parts.append(chunk)
                buffer = []
                continue
            buffer.append(char)

        tail = "".join(buffer).strip()
        if tail:
            parts.append(tail)
        return parts

    @staticmethod
    def _extract_param_section(header_text: str) -> str:
        """Extract the top-level procedure/function parameter section."""
        start = header_text.find("(")
        if start < 0:
            return ""
        depth = 0
        for index in range(start, len(header_text)):
            char = header_text[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return header_text[start + 1 : index]
        return ""

    def _fallback_parameters(self, object_text: str) -> List[Dict[str, str]]:
        """Extract procedure/function parameters using regex fallback."""
        is_as_match = re.search(r"\b(?:is|as)\b", object_text, flags=re.IGNORECASE)
        header = object_text[: is_as_match.start()] if is_as_match else object_text[:600]
        param_block = self._extract_param_section(header)
        if not param_block:
            return []

        parameters: List[Dict[str, str]] = []
        for raw_param in self._split_top_level_csv(param_block):
            normalized = " ".join(raw_param.split())
            match = PARAM_PATTERN.match(normalized)
            if not match:
                continue
            name, direction, datatype = match.groups()
            parameters.append(
                {
                    "name": self._normalize_name(name),
                    "type": datatype.strip().upper(),
                    "mode": (direction or "IN").upper(),
                }
            )
        return parameters

    @staticmethod
    def _fallback_sql_statements(object_text: str) -> List[Dict[str, str]]:
        """Extract SQL statements from a block for dependency analysis."""
        statements: List[Dict[str, str]] = []
        for match in re.finditer(
            r"(?is)\b(select|insert|update|delete|merge)\b.*?(?:;|$)",
            object_text,
        ):
            statement = " ".join(match.group(0).split())
            if statement:
                statements.append({"type": "sql_statement", "text": statement})
        return statements

    @staticmethod
    def _fallback_exceptions(object_text: str) -> List[Dict[str, Any]]:
        """Extract exception handlers from an object block."""
        handlers = []
        for match in re.finditer(r"\bwhen\s+([A-Za-z_][\w$#]*)\s+then\b", object_text, flags=re.IGNORECASE):
            handlers.append({"exception": match.group(1).upper(), "statements": []})
        return handlers

    def _fallback_parse(self, content: str) -> Optional[Dict[str, Any]]:
        """Build a lightweight AST when ANTLR parse fails."""
        matches = list(OBJECT_DECL_PATTERN.finditer(content))
        if not matches:
            return None

        ast: Dict[str, Any] = {
            "type": "plsql_file",
            "procedures": [],
            "functions": [],
            "triggers": [],
            "packages": [],
            "declarations": [],
            "executables": [],
            "exceptions": [],
        }

        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            object_text = content[start:end]
            object_type = match.group(1).upper().replace(" BODY", "")
            object_name = self._normalize_name(match.group(2))

            if object_type == "PROCEDURE":
                ast["procedures"].append(
                    {
                        "type": "procedure",
                        "name": object_name,
                        "parameters": self._fallback_parameters(object_text),
                        "variables": [],
                        "statements": self._fallback_sql_statements(object_text),
                        "exceptions": self._fallback_exceptions(object_text),
                    }
                )
            elif object_type == "FUNCTION":
                return_match = re.search(r"\breturn\s+([A-Za-z_][\w$#]*(?:\([^)]*\))?)", object_text, re.IGNORECASE)
                ast["functions"].append(
                    {
                        "type": "function",
                        "name": object_name,
                        "parameters": self._fallback_parameters(object_text),
                        "return_type": return_match.group(1).upper() if return_match else "UNKNOWN",
                        "variables": [],
                        "statements": self._fallback_sql_statements(object_text),
                        "exceptions": self._fallback_exceptions(object_text),
                    }
                )
            elif object_type == "TRIGGER":
                ast["triggers"].append(
                    {
                        "type": "trigger",
                        "name": object_name,
                        "timing": None,
                        "event": None,
                        "table": None,
                        "statements": self._fallback_sql_statements(object_text),
                    }
                )
            elif object_type == "PACKAGE":
                ast["packages"].append(
                    {
                        "type": "package",
                        "name": object_name,
                        "procedures": [],
                        "functions": [],
                        "variables": [],
                        "constants": [],
                        "types": [],
                    }
                )

        return ast
    
    def parse(self, content: str) -> Dict[str, Any]:
        """
        Parse PL/SQL content and generate AST
        
        Args:
            content (str): PL/SQL content to parse
            
        Returns:
            Dict[str, Any]: Generated AST
        """
        if not content or not content.strip():
            raise PLSQLParseError("Empty PL/SQL content provided")
        
        content = preprocess_plsql_for_parser(content)
        
        if PlSqlLexer is None or PlSqlParser is None:
            raise PLSQLParseError(
                "ANTLR parsers are not available. Generate parser files under src/parser/generated first."
            )
        
        try:
            # Create input stream
            input_stream = InputStream(content)
            
            # Create lexer
            lexer = PlSqlLexer(input_stream)
            lexer.removeErrorListeners()
            error_listener = PLSQLErrorListener()
            lexer.addErrorListener(error_listener)
            
            # Create token stream
            token_stream = CommonTokenStream(lexer)
            
            # Create parser
            parser = PlSqlParser(token_stream)
            parser.removeErrorListeners()
            parser.addErrorListener(error_listener)
            
            # Parse
            tree = parser.sql_script()
            
            # Check for parsing errors
            if error_listener.errors:
                error_msg = f"PL/SQL parsing failed with {len(error_listener.errors)} errors: {'; '.join(error_listener.errors)}"
                raise PLSQLParseError(error_msg)
            
            # Build AST
            ast_builder = PLSQLASTBuilder()
            walker = ParseTreeWalker()
            walker.walk(ast_builder, tree)
            
            logger.info(f"Successfully parsed PL/SQL content with {len(ast_builder.ast['procedures'])} procedures, "
                       f"{len(ast_builder.ast['functions'])} functions, "
                       f"{len(ast_builder.ast['triggers'])} triggers, "
                       f"{len(ast_builder.ast['packages'])} packages")
            
            return ast_builder.ast
            
        except Exception as e:
            fallback_ast = self._fallback_parse(content)
            if fallback_ast:
                logger.warning(
                    "ANTLR parse failed; using fallback parser for object extraction. Error: %s",
                    str(e),
                )
                return fallback_ast
            logger.error(f"Failed to parse PL/SQL content: {str(e)}")
            raise PLSQLParseError(f"PL/SQL parsing failed: {str(e)}")
    
    def parse_procedure(self, content: str) -> Dict[str, Any]:
        """
        Parse a single PL/SQL procedure
        
        Args:
            content (str): PL/SQL procedure content
            
        Returns:
            Dict[str, Any]: Parsed procedure AST
        """
        try:
            content = preprocess_plsql_for_parser(content)
            input_stream = InputStream(content)
            lexer = PlSqlLexer(input_stream)
            token_stream = CommonTokenStream(lexer)
            parser = PlSqlParser(token_stream)
            
            # Parse procedure
            tree = parser.create_procedure_body()
            
            # Extract procedure information
            procedure_info = {
                'name': _ctx_text(tree.procedure_name(), "anonymous_procedure"),
                'parameters': [],
                'body': content
            }
            
            # Extract parameters
            for param in tree.parameter():
                param_info = {
                    'name': _ctx_text(param.parameter_name(), "param"),
                    'type': _ctx_text(param.datatype(), "UNKNOWN"),
                    'mode': _ctx_text(param.parameter_mode(), 'IN')
                }
                procedure_info['parameters'].append(param_info)
            
            return procedure_info
            
        except Exception as e:
            logger.error(f"Failed to parse PL/SQL procedure: {str(e)}")
            raise PLSQLParseError(f"Procedure parsing failed: {str(e)}")
    
    def parse_function(self, content: str) -> Dict[str, Any]:
        """
        Parse a single PL/SQL function
        
        Args:
            content (str): PL/SQL function content
            
        Returns:
            Dict[str, Any]: Parsed function AST
        """
        try:
            content = preprocess_plsql_for_parser(content)
            input_stream = InputStream(content)
            lexer = PlSqlLexer(input_stream)
            token_stream = CommonTokenStream(lexer)
            parser = PlSqlParser(token_stream)
            
            # Parse function
            tree = parser.create_function_body()
            
            # Extract function information
            function_info = {
                'name': _ctx_text(tree.function_name(), "anonymous_function"),
                'parameters': [],
                'return_type': _ctx_text(tree.datatype(), "UNKNOWN"),
                'body': content
            }
            
            # Extract parameters
            for param in tree.parameter():
                param_info = {
                    'name': _ctx_text(param.parameter_name(), "param"),
                    'type': _ctx_text(param.datatype(), "UNKNOWN"),
                    'mode': _ctx_text(param.parameter_mode(), 'IN')
                }
                function_info['parameters'].append(param_info)
            
            return function_info
            
        except Exception as e:
            logger.error(f"Failed to parse PL/SQL function: {str(e)}")
            raise PLSQLParseError(f"Function parsing failed: {str(e)}")
    
    def parse_trigger(self, content: str) -> Dict[str, Any]:
        """
        Parse a single PL/SQL trigger
        
        Args:
            content (str): PL/SQL trigger content
            
        Returns:
            Dict[str, Any]: Parsed trigger AST
        """
        try:
            content = preprocess_plsql_for_parser(content)
            input_stream = InputStream(content)
            lexer = PlSqlLexer(input_stream)
            token_stream = CommonTokenStream(lexer)
            parser = PlSqlParser(token_stream)
            
            # Parse trigger
            tree = parser.create_trigger()
            
            # Extract trigger information
            trigger_info = {
                'name': _ctx_text(tree.trigger_name(), "anonymous_trigger"),
                'timing': _ctx_text(tree.trigger_timing(), "unknown"),
                'event': _ctx_text(tree.triggering_event(), "unknown"),
                'table': _ctx_text(tree.table_name(), "unknown"),
                'body': content
            }
            
            return trigger_info
            
        except Exception as e:
            logger.error(f"Failed to parse PL/SQL trigger: {str(e)}")
            raise PLSQLParseError(f"Trigger parsing failed: {str(e)}")
    
    def extract_sql_statements(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract SQL statements from AST
        
        Args:
            ast (Dict[str, Any]): PL/SQL AST
            
        Returns:
            List[Dict[str, Any]]: List of SQL statements
        """
        sql_statements = []
        
        def extract_from_object(obj):
            if isinstance(obj, dict):
                if obj.get('type') == 'sql_statement':
                    sql_statements.append(obj)
                for value in obj.values():
                    extract_from_object(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_from_object(item)
        
        extract_from_object(ast)
        return sql_statements
    
    def extract_variables(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract variable declarations from AST
        
        Args:
            ast (Dict[str, Any]): PL/SQL AST
            
        Returns:
            List[Dict[str, Any]]: List of variable declarations
        """
        variables = []
        
        def extract_from_object(obj):
            if isinstance(obj, dict):
                if obj.get('type') == 'variable':
                    variables.append(obj)
                for value in obj.values():
                    extract_from_object(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_from_object(item)
        
        extract_from_object(ast)
        return variables
    
    def extract_procedures(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract procedure definitions from AST
        
        Args:
            ast (Dict[str, Any]): PL/SQL AST
            
        Returns:
            List[Dict[str, Any]]: List of procedure definitions
        """
        return ast.get('procedures', [])
    
    def extract_functions(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract function definitions from AST
        
        Args:
            ast (Dict[str, Any]): PL/SQL AST
            
        Returns:
            List[Dict[str, Any]]: List of function definitions
        """
        return ast.get('functions', [])
    
    def extract_triggers(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract trigger definitions from AST
        
        Args:
            ast (Dict[str, Any]): PL/SQL AST
            
        Returns:
            List[Dict[str, Any]]: List of trigger definitions
        """
        return ast.get('triggers', [])
    
    def extract_packages(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract package definitions from AST
        
        Args:
            ast (Dict[str, Any]): PL/SQL AST
            
        Returns:
            List[Dict[str, Any]]: List of package definitions
        """
        return ast.get('packages', [])
    
    def validate_syntax(self, content: str) -> bool:
        """
        Validate PL/SQL syntax
        
        Args:
            content (str): PL/SQL content to validate
            
        Returns:
            bool: True if syntax is valid
        """
        try:
            self.parse(content)
            return True
        except PLSQLParseError:
            return False
    
    def get_parse_tree(self, content: str) -> Any:
        """
        Get ANTLR parse tree for debugging
        
        Args:
            content (str): PL/SQL content
            
        Returns:
            Any: ANTLR parse tree
        """
        try:
            input_stream = InputStream(content)
            lexer = PlSqlLexer(input_stream)
            token_stream = CommonTokenStream(lexer)
            parser = PlSqlParser(token_stream)
            
            return parser.sql_script()
        except Exception as e:
            logger.error(f"Failed to generate parse tree: {str(e)}")
            return None


def create_sample_antlr_grammar():
    """
    Create a sample ANTLR grammar file for PL/SQL
    This is a simplified version for demonstration
    """
    grammar_content = """
grammar PlSql;

sql_script
    : (create_procedure_body | create_function_body | create_trigger | create_package | anonymous_block)* EOF
    ;

create_procedure_body
    : CREATE (OR REPLACE)? PROCEDURE procedure_name parameter_list?
      (IS | AS)
      (declare_section)?
      BEGIN
      executable_section
      (EXCEPTION exception_section)?
      END (procedure_name)?
    ;

create_function_body
    : CREATE (OR REPLACE)? FUNCTION function_name parameter_list?
      RETURN datatype
      (IS | AS)
      (declare_section)?
      BEGIN
      executable_section
      (EXCEPTION exception_section)?
      END (function_name)?
    ;

create_trigger
    : CREATE (OR REPLACE)? TRIGGER trigger_name
      trigger_timing triggering_event ON table_name
      (FOR EACH ROW)?
      (WHEN condition)?
      (IS | AS)
      BEGIN
      executable_section
      END
    ;

create_package
    : CREATE (OR REPLACE)? PACKAGE package_name
      (IS | AS)
      package_specification
      END package_name
    ;

anonymous_block
    : (DECLARE declare_section)?
      BEGIN
      executable_section
      (EXCEPTION exception_section)?
      END
    ;

procedure_name
    : identifier
    ;

function_name
    : identifier
    ;

trigger_name
    : identifier
    ;

package_name
    : identifier
    ;

table_name
    : identifier
    ;

identifier
    : ID
    | STRING_LITERAL
    ;

parameter_list
    : '(' parameter (',' parameter)* ')'
    ;

parameter
    : parameter_name datatype (parameter_mode)?
    ;

parameter_name
    : identifier
    ;

parameter_mode
    : IN | OUT | IN OUT
    ;

datatype
    : identifier (precision_scale?)?
    | VARCHAR2 | NUMBER | DATE | BOOLEAN
    ;

precision_scale
    : '(' NUMBER_LITERAL (',' NUMBER_LITERAL)? ')'
    ;

declare_section
    : (variable_declaration | constant_declaration | type_declaration)*
    ;

variable_declaration
    : variable_name datatype (:= expression)?
    ;

constant_declaration
    : variable_name CONSTANT datatype := expression
    ;

type_declaration
    : TYPE type_name IS datatype
    ;

executable_section
    : (statement | if_statement | loop_statement | sql_statement)*
    ;

statement
    : assignment_statement
    | procedure_call
    | return_statement
    ;

assignment_statement
    : variable_name ':=' expression
    ;

if_statement
    : IF condition THEN
      executable_section
      (ELSIF condition THEN executable_section)*
      (ELSE executable_section)?
      END IF
    ;

loop_statement
    : (FOR | WHILE | LOOP)
      executable_section
      END LOOP
    ;

sql_statement
    : select_statement
    | insert_statement
    | update_statement
    | delete_statement
    | merge_statement
    ;

select_statement
    : SELECT select_list FROM table_list (WHERE condition)? (ORDER BY order_list)?
    ;

insert_statement
    : INSERT INTO table_name VALUES '(' expression_list ')'
    | INSERT INTO table_name '(' column_list ')' VALUES '(' expression_list ')'
    ;

update_statement
    : UPDATE table_name SET assignment_list (WHERE condition)?
    ;

delete_statement
    : DELETE FROM table_name (WHERE condition)?
    ;

merge_statement
    : MERGE INTO table_name USING table_reference ON condition
      (WHEN MATCHED THEN update_statement | WHEN NOT MATCHED THEN insert_statement)
    ;

exception_section
    : exception_handler+
    ;

exception_handler
    : WHEN exception_name THEN executable_section
    ;

condition
    : expression (AND | OR | NOT)* expression
    ;

expression
    : term ((PLUS | MINUS) term)*
    ;

term
    : factor ((MULT | DIV) factor)*
    ;

factor
    : NUMBER_LITERAL
    | STRING_LITERAL
    | variable_name
    | function_call
    | '(' expression ')'
    ;

function_call
    : function_name '(' expression_list? ')'
    ;

procedure_call
    : procedure_name '(' expression_list? ')'
    ;

expression_list
    : expression (',' expression)*
    ;

select_list
    : '*' | expression (',' expression)*
    ;

table_list
    : table_name (',' table_name)*
    ;

column_list
    : identifier (',' identifier)*
    ;

assignment_list
    : assignment_statement (',' assignment_statement)*
    ;

order_list
    : expression (ASC | DESC)? (',' expression (ASC | DESC)?)*
    ;

trigger_timing
    : BEFORE | AFTER | INSTEAD OF
    ;

triggering_event
    : INSERT | UPDATE | DELETE | UPDATE OF column_list
    ;

exception_name
    : identifier | OTHERS
    ;

// Lexer rules
ID: [a-zA-Z_][a-zA-Z0-9_]*;
NUMBER_LITERAL: [0-9]+;
STRING_LITERAL: '\'' (~'\'')* '\'';
WS: [ \t\r\n]+ -> skip;
COMMENT: '--' .*? '\r'? '\n' -> skip;
MULTILINE_COMMENT: '/*' .*? '*/' -> skip;

// Keywords
CREATE: 'CREATE';
OR: 'OR';
REPLACE: 'REPLACE';
PROCEDURE: 'PROCEDURE';
FUNCTION: 'FUNCTION';
TRIGGER: 'TRIGGER';
PACKAGE: 'PACKAGE';
TYPE: 'TYPE';
IS: 'IS';
AS: 'AS';
BEGIN: 'BEGIN';
END: 'END';
DECLARE: 'DECLARE';
EXCEPTION: 'EXCEPTION';
WHEN: 'WHEN';
THEN: 'THEN';
ELSE: 'ELSE';
ELSIF: 'ELSIF';
IF: 'IF';
LOOP: 'LOOP';
FOR: 'FOR';
WHILE: 'WHILE';
RETURN: 'RETURN';
CONSTANT: 'CONSTANT';
VARIABLE: 'VARIABLE';
CURSOR: 'CURSOR';
SELECT: 'SELECT';
FROM: 'FROM';
WHERE: 'WHERE';
ORDER: 'ORDER';
BY: 'BY';
ASC: 'ASC';
DESC: 'DESC';
INSERT: 'INSERT';
INTO: 'INTO';
VALUES: 'VALUES';
UPDATE: 'UPDATE';
SET: 'SET';
DELETE: 'DELETE';
MERGE: 'MERGE';
USING: 'USING';
ON: 'ON';
WHEN: 'WHEN';
MATCHED: 'MATCHED';
NOT: 'NOT';
BEFORE: 'BEFORE';
AFTER: 'AFTER';
INSTEAD: 'INSTEAD';
OF: 'OF';
IN: 'IN';
OUT: 'OUT';
VARCHAR2: 'VARCHAR2';
NUMBER: 'NUMBER';
DATE: 'DATE';
BOOLEAN: 'BOOLEAN';
PLUS: '+';
MINUS: '-';
MULT: '*';
DIV: '/';
"""
    
    # Create ANTLR directory if it doesn't exist
    antlr_dir = Path(__file__).parent
    antlr_dir.mkdir(exist_ok=True)
    
    # Write grammar file
    grammar_file = antlr_dir / 'PlSql.g4'
    with open(grammar_file, 'w') as f:
        f.write(grammar_content)
    
    logger.info(f"Sample ANTLR grammar created at: {grammar_file}")
    return grammar_file
