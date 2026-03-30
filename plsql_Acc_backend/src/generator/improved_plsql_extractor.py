"""
Enhanced PL/SQL Logic Extractor

Extracts actual business logic from PL/SQL procedure bodies.
Handles validations, calculations, DML, returns, and transactions.
"""
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExtractedLogic:
    """Extracted logic patterns from PL/SQL procedure"""
    validations: List[Dict[str, str]] = field(default_factory=list)             # Assertions/validations
    validations_chain: List[str] = field(default_factory=list)                   # Multi-step validation strings
    calculations: List[Dict[str, str]] = field(default_factory=list)             # Variable assignments
    derived_values: List[Dict[str, str]] = field(default_factory=list)           # Complex derived values (coalesce, case, etc.)
    inserts: List[Dict[str, Any]] = field(default_factory=list)                  # INSERT statements
    updates: List[Dict[str, Any]] = field(default_factory=list)                  # UPDATE statements
    deletes: List[Dict[str, Any]] = field(default_factory=list)                  # DELETE statements
    selects: List[Dict[str, Any]] = field(default_factory=list)                  # SELECT statements
    returns: List[str] = field(default_factory=list)                             # RETURN statements
    has_commit: bool = False                                                     # Has COMMIT
    exceptions_raised: List[Dict[str, str]] = field(default_factory=list)        # RAISE_APPLICATION_ERROR calls
    function_calls: List[Dict[str, Any]] = field(default_factory=list)           # Function/procedure calls
    logging_calls: List[Dict[str, Any]] = field(default_factory=list)            # appl_log_pkg.log calls
    error_assertions: List[Dict[str, str]] = field(default_factory=list)         # appl_error_pkg.assert calls
    procedure_parameters: List[Dict[str, str]] = field(default_factory=list)     # Extracted IN/OUT parameters from signature
    return_type: str = ''                                                        # Extracted return type for functions


class ImprovedPLSQLExtractor:
    """Extract business logic from PL/SQL procedure bodies"""
    
    @staticmethod
    def extract_all_logic(proc_body: str) -> ExtractedLogic:
        """
        Extract all business logic from PL/SQL procedure body.
        """
        logic = ExtractedLogic()
        
        # Normalize the body
        body = proc_body.strip()
        
        # Extract procedure parameters and return type from header
        ImprovedPLSQLExtractor._extract_procedure_signature(body, logic)
        
        # Extract validations (IF...THEN with RAISE_APPLICATION_ERROR)
        ImprovedPLSQLExtractor._extract_validations(body, logic)
        
        # Extract error assertions (appl_error_pkg.assert calls)
        ImprovedPLSQLExtractor._extract_error_assertions(body, logic)
        
        # Extract function calls (package.function(...) patterns)
        ImprovedPLSQLExtractor._extract_function_calls(body, logic)
        
        # Extract logging calls (appl_log_pkg.log patterns)
        ImprovedPLSQLExtractor._extract_logging_calls(body, logic)
        
        # Extract derived values (coalesce, case, nvl patterns)
        ImprovedPLSQLExtractor._extract_derived_values(body, logic)
        
        # Extract variable assignments (calculations)
        ImprovedPLSQLExtractor._extract_calculations(body, logic)
        
        # Extract DML statements
        ImprovedPLSQLExtractor._extract_inserts(body, logic)
        ImprovedPLSQLExtractor._extract_updates(body, logic)
        ImprovedPLSQLExtractor._extract_deletes(body, logic)
        ImprovedPLSQLExtractor._extract_selects(body, logic)
        
        # Extract RETURN statements
        ImprovedPLSQLExtractor._extract_returns(body, logic)
        
        # Check for transactions
        logic.has_commit = 'COMMIT' in body.upper()
        
        # Extract exception handling
        ImprovedPLSQLExtractor._extract_exceptions(body, logic)
        
        return logic
    
    @staticmethod
    def _extract_procedure_signature(body: str, logic: ExtractedLogic):
        """
        Extract procedure/function parameters and return type from the signature.
        Handles both CREATE OR REPLACE PROCEDURE and CREATE OR REPLACE FUNCTION.
        
        Patterns:
        PROCEDURE name (param1 IN type1, param2 OUT type2) AS
        FUNCTION name (param1 IN type1) RETURN number AS
        FUNCTION name (param1 IN type1) RETURN xy_customer%rowtype AS
        """
        # Try to find PROCEDURE or FUNCTION keyword with its signature
        # Match: PROCEDURE/FUNCTION name (params) [RETURN type] where type can include %rowtype
        proc_pattern = r'(?:PROCEDURE|FUNCTION)\s+\w+\s*\(\s*([^)]*)\s*\)\s*(?:RETURN\s+([^AS\n]+?))?\s*(?:AS|IS)'
        match = re.search(proc_pattern, body, re.IGNORECASE | re.DOTALL)
        
        if match:
            params_str = match.group(1)
            return_type = match.group(2)
            
            # Store return type if present
            if return_type:
                return_type = return_type.strip()
                logic.return_type = return_type.upper()
            
            # Extract individual parameters
            if params_str.strip():
                params = ImprovedPLSQLExtractor._parse_parameters(params_str)
                logic.procedure_parameters = params
    
    @staticmethod
    def _parse_parameters(params_str: str) -> List[Dict[str, str]]:
        """
        Parse parameter list from procedure/function signature.
        Example: "p_id IN NUMBER, p_name IN VARCHAR2, p_result OUT VARCHAR2"
        """
        params = []
        
        # Split by comma, but be careful about commas within type names
        # Simple approach: split by comma and process each
        param_parts = [p.strip() for p in params_str.split(',')]
        
        for part in param_parts:
            if not part:
                continue
            
            # Match: param_name [IN|OUT|IN OUT] type_name [DEFAULT value]
            pattern = r'(\w+)\s+(?:(IN|OUT|IN\s+OUT)\s+)?(\w+)(?:\s*:=\s*[^\s,]+)?'
            match = re.match(pattern, part, re.IGNORECASE)
            
            if match:
                param_name = match.group(1)
                direction = match.group(2) or 'IN'
                param_type = match.group(3)
                
                # Normalize
                direction = direction.upper().replace(' ', '_')
                
                params.append({
                    'name': param_name,
                    'direction': direction,
                    'plsql_type': param_type.upper()
                })
        
        return params
    
    @staticmethod
    def _extract_validations(body: str, logic: ExtractedLogic):
        """
        Extract validation patterns.
        Pattern: IF condition THEN RAISE_APPLICATION_ERROR(code, 'message' or variable)
        """
        # Match: IF ... THEN RAISE_APPLICATION_ERROR with either string or variable
        # Support both quoted strings and variable names as error message
        pattern = r"IF\s+(.+?)\s+THEN\s+RAISE_APPLICATION_ERROR\s*\(\s*-?(\d+)\s*,\s*(?:'([^']*)'|(\w+))"
        
        for match in re.finditer(pattern, body, re.IGNORECASE | re.DOTALL):
            condition = match.group(1).strip()
            error_code = match.group(2)
            message = match.group(3) if match.group(3) else f"[{match.group(4)}]"  # Use variable name in brackets if no string
            
            logic.validations.append({
                'condition': condition,
                'error_code': error_code,
                'message': message,
                'field': ImprovedPLSQLExtractor._extract_field_from_condition(condition)
            })
    
    @staticmethod
    def _extract_field_from_condition(condition: str) -> str:
        """Extract field name from validation condition"""
        # IS NULL checks
        match = re.search(r'(\w+)\s+IS\s+(?:NOT\s+)?NULL', condition, re.IGNORECASE)
        if match:
            return match.group(1).lower()
        
        # Comparison checks
        match = re.search(r'(\w+)\s*[<>=!]+', condition)
        if match:
            return match.group(1).lower()
        
        return 'unknown'
    
    @staticmethod
    def _extract_calculations(body: str, logic: ExtractedLogic):
        """
        Extract variable assignments (calculations).
        Pattern: variable := expression;
        """
        # Match: l_variable := expression;
        pattern = r'([lv]_\w+)\s*:=\s*([^;]+);'
        
        for match in re.finditer(pattern, body, re.IGNORECASE):
            variable = match.group(1).strip()
            expression = match.group(2).strip()
            
            logic.calculations.append({
                'variable': variable,
                'expression': expression
            })
    
    @staticmethod
    def _extract_inserts(body: str, logic: ExtractedLogic):
        """
        Extract INSERT statements, including RETURNING clauses.
        Patterns:
        - INSERT INTO table (columns) VALUES (values);
        - INSERT INTO table (columns) VALUES (values) RETURNING column INTO variable;
        - INSERT INTO table VALUES record;
        """
        # Pattern 1: INSERT INTO ... VALUES ... [RETURNING ... INTO ...]
        pattern = r"INSERT\s+INTO\s+(\w+)\s*(?:\((.*?)\))?\s*VALUES\s*\((.*?)\)(?:\s+RETURNING\s+(\w+)\s+INTO\s+(\w+))?"
        
        for match in re.finditer(pattern, body, re.IGNORECASE | re.DOTALL):
            table = match.group(1).strip()
            columns_str = match.group(2)
            values_str = match.group(3)
            returning_column = match.group(4)  # The column being returned (e.g., 'customer_id')
            returning_into = match.group(5)    # The variable receiving it (e.g., 'l_returnvalue')
            
            columns = [c.strip() for c in columns_str.split(',')] if columns_str else []
            values = [v.strip() for v in values_str.split(',')]
            
            insert_info = {
                'table': table,
                'columns': columns,
                'values': values
            }
            
            # Capture RETURNING info for return type inference
            if returning_column and returning_into:
                insert_info['returning_column'] = returning_column.strip()
                insert_info['returning_into'] = returning_into.strip()
            
            logic.inserts.append(insert_info)
        
        # Pattern 2: INSERT INTO table VALUES record (for %rowtype inserts)
        pattern2 = r"INSERT\s+INTO\s+(\w+)\s+VALUES\s+(\w+)(?:\s+RETURNING\s+(\w+)\s+INTO\s+(\w+))?"
        
        for match in re.finditer(pattern2, body, re.IGNORECASE):
            table = match.group(1).strip()
            record = match.group(2).strip()
            returning_column = match.group(3)
            returning_into = match.group(4)
            
            insert_info = {
                'table': table,
                'record_value': record,
                'is_record_insert': True
            }
            
            if returning_column and returning_into:
                insert_info['returning_column'] = returning_column.strip()
                insert_info['returning_into'] = returning_into.strip()
            
            logic.inserts.append(insert_info)
    
    @staticmethod
    def _extract_updates(body: str, logic: ExtractedLogic):
        """
        Extract UPDATE statements.
        Pattern: UPDATE table SET column=value WHERE condition;
        """
        pattern = r"UPDATE\s+(\w+)\s+SET\s+(.+?)\s+(?:WHERE|;)"
        
        for match in re.finditer(pattern, body, re.IGNORECASE):
            table = match.group(1).strip()
            assignments_str = match.group(2)
            
            assignments = {}
            for assign in assignments_str.split(','):
                if '=' in assign:
                    col, val = assign.split('=', 1)
                    assignments[col.strip()] = val.strip()
            
            logic.updates.append({
                'table': table,
                'assignments': assignments
            })
    
    @staticmethod
    def _extract_deletes(body: str, logic: ExtractedLogic):
        """
        Extract DELETE statements.
        """
        pattern = r"DELETE\s+FROM\s+(\w+)\s+(?:WHERE\s+(.+?))?;"
        
        for match in re.finditer(pattern, body, re.IGNORECASE):
            table = match.group(1).strip()
            where = match.group(2).strip() if match.group(2) else None
            
            logic.deletes.append({
                'table': table,
                'where': where
            })
    
    @staticmethod
    def _extract_selects(body: str, logic: ExtractedLogic):
        """
        Extract SELECT statements (INTO variables), including NO_DATA_FOUND handling.
        
        Patterns:
        - BEGIN SELECT ... INTO ... FROM ... WHERE ...; EXCEPTION WHEN no_data_found THEN ... END;
        - SELECT ... INTO ... FROM ... WHERE ...;
        """
        # Pattern with exception handling: BEGIN...SELECT...INTO...EXCEPTION WHEN no_data_found...END
        exception_pattern = r"BEGIN\s+SELECT\s+(.+?)\s+INTO\s+(.+?)\s+FROM\s+(\w+)(?:\s+WHERE\s+(.+?))?\s*;?\s*EXCEPTION\s+WHEN\s+NO_DATA_FOUND\s+THEN\s+(.+?)\s+END"
        
        for match in re.finditer(exception_pattern, body, re.IGNORECASE | re.DOTALL):
            columns = match.group(1).strip()
            into_vars = match.group(2).strip()
            table = match.group(3).strip()
            where = match.group(4).strip() if match.group(4) else None
            exception_handling = match.group(5).strip()
            
            logic.selects.append({
                'columns': columns,
                'into_variables': into_vars,
                'table': table,
                'where': where,
                'no_data_found_handling': exception_handling,
                'has_exception': True
            })
        
        # Pattern without exception handling
        pattern = r"SELECT\s+(.+?)\s+INTO\s+(.+?)\s+FROM\s+(\w+)(?:\s+WHERE\s+(.+?))?(?:;|\s+(?:WHERE|AND|OR|UNION|INTERSECT|EXCEPT|ORDER|GROUP))"
        
        for match in re.finditer(pattern, body, re.IGNORECASE):
            columns = match.group(1).strip()
            into_vars = match.group(2).strip()
            table = match.group(3).strip()
            where = match.group(4).strip() if match.group(4) else None
            
            # Skip if we already captured this with exception handling
            if not any(s.get('into_variables') == into_vars and s.get('table') == table for s in logic.selects):
                logic.selects.append({
                    'columns': columns,
                    'into_variables': into_vars,
                    'table': table,
                    'where': where,
                    'has_exception': False
                })
    
    @staticmethod
    def _extract_returns(body: str, logic: ExtractedLogic):
        """
        Extract RETURN statements.
        """
        pattern = r"RETURN\s+(\w+)\s*;"
        
        for match in re.finditer(pattern, body, re.IGNORECASE):
            return_var = match.group(1).strip()
            logic.returns.append(return_var)
    
    @staticmethod
    def _extract_error_assertions(body: str, logic: ExtractedLogic):
        """
        Extract appl_error_pkg.assert calls - validation assertions
        Pattern: appl_error_pkg.assert(p_condition is not null, 'Error message');
        """
        pattern = r"appl_error_pkg\.assert\s*\(\s*([^,]+?)\s*,\s*'([^']*)'\s*\)"
        
        for match in re.finditer(pattern, body, re.IGNORECASE | re.DOTALL):
            condition = match.group(1).strip()
            message = match.group(2).strip()
            
            logic.error_assertions.append({
                'condition': condition,
                'message': message
            })
            
            # Build validation chain
            logic.validations_chain.append(f"assert({condition}) => {message}")
    
    @staticmethod
    def _extract_function_calls(body: str, logic: ExtractedLogic):
        """
        Extract function/procedure calls to packages
        Pattern: package_name.function_name(param1 => val1, param2 => val2)
        or: l_var := package_name.function_name(params)
        """
        # Pattern: package.function(... => ...)
        pattern = r"(\w+)\.(\w+)\s*\(\s*([^)]*)\s*\)"
        
        for match in re.finditer(pattern, body, re.IGNORECASE):
            package = match.group(1).strip()
            function = match.group(2).strip()
            params = match.group(3).strip()
            
            logic.function_calls.append({
                'package': package,
                'function': function,
                'params': params,
                'full_call': f"{package}.{function}({params})"
            })
    
    @staticmethod
    def _extract_logging_calls(body: str, logic: ExtractedLogic):
        """
        Extract appl_log_pkg.log calls
        Pattern: appl_log_pkg.log('message', p_level => appl_log_pkg.c_log_level_debug)
        """
        pattern = r"appl_log_pkg\.log\s*\(\s*'([^']*)'\s*(?:,\s*p_level\s*=>\s*([^)]+))?\s*\)"
        
        for match in re.finditer(pattern, body, re.IGNORECASE):
            message = match.group(1).strip()
            level = match.group(2).strip() if match.group(2) else 'INFO'
            
            logic.logging_calls.append({
                'message': message,
                'level': level
            })
    
    @staticmethod
    def _extract_balanced_parens(text: str, start_pos: int) -> str:
        """
        Extract content between balanced parentheses starting at start_pos.
        
        Args:
            text: The text to extract from
            start_pos: Position of the opening paren
            
        Returns:
            Content between balanced parentheses (excluding the parens)
        """
        if start_pos >= len(text) or text[start_pos] != '(':
            return ""
        
        paren_count = 1
        pos = start_pos + 1
        
        while pos < len(text) and paren_count > 0:
            if text[pos] == '(':
                paren_count += 1
            elif text[pos] == ')':
                paren_count -= 1
            pos += 1
        
        # Return content between parens (excluding the parens themselves)
        return text[start_pos + 1:pos - 1]
    
    @staticmethod
    def _extract_derived_values(body: str, logic: ExtractedLogic):
        """
        Extract complex derived values: coalesce, case statements, function calls
        Pattern: l_var := coalesce(...) or variable := case ... end
        Uses balanced parentheses extraction to handle nested function calls.
        """
        # First, find all COALESCE assignments with balanced paren extraction
        coalesce_pattern = r"(\w+)\s*:=\s*coalesce\s*\("
        for match in re.finditer(coalesce_pattern, body, re.IGNORECASE):
            var = match.group(1).strip()
            paren_start = match.end() - 1  # Position of the opening paren
            coalesce_content = ImprovedPLSQLExtractor._extract_balanced_parens(body, paren_start)
            
            if coalesce_content:
                full_expr = f"{var} := COALESCE({coalesce_content})"
                logic.derived_values.append({
                    'variable': var,
                    'type': 'coalesce',
                    'expression': full_expr
                })
        
        # Find NVL/IFNULL assignments
        nvl_pattern = r"(\w+)\s*:=\s*(?:nvl|ifnull)\s*\("
        for match in re.finditer(nvl_pattern, body, re.IGNORECASE):
            var = match.group(1).strip()
            paren_start = match.end() - 1
            nvl_content = ImprovedPLSQLExtractor._extract_balanced_parens(body, paren_start)
            
            if nvl_content:
                full_expr = f"{var} := NVL({nvl_content})"
                logic.derived_values.append({
                    'variable': var,
                    'type': 'nvl',
                    'expression': full_expr
                })
        
        # Find CASE statements
        case_pattern = r"(\w+)\s*:=\s*case\s+.+?\s+end"
        for match in re.finditer(case_pattern, body, re.IGNORECASE | re.DOTALL):
            var = match.group(1).strip()
            expr = match.group(0).strip()
            
            logic.derived_values.append({
                'variable': var,
                'type': 'case',
                'expression': expr
            })
    
    @staticmethod
    def _extract_exceptions(body: str, logic: ExtractedLogic):
        """
        Extract RAISE_APPLICATION_ERROR calls.
        """
        pattern = r"RAISE_APPLICATION_ERROR\s*\(\s*-?(\d+)\s*,\s*'([^']*)'\s*\)"
        
        for match in re.finditer(pattern, body, re.IGNORECASE):
            error_code = match.group(1)
            message = match.group(2)
            
            logic.exceptions_raised.append({
                'code': error_code,
                'message': message
            })


def extract_full_procedure_body(source: str, proc_name: str) -> Optional[str]:
    """
    Extract the complete procedure body from source code.
    Handles nested BEGIN/END blocks properly.
    """
    # Find procedure start
    pattern = rf'(?:CREATE\s+OR\s+REPLACE\s+)?PROCEDURE\s+{re.escape(proc_name)}\s*\(.*?\)\s*(?:IS|AS)'
    start_match = re.search(pattern, source, re.IGNORECASE | re.DOTALL)
    
    if not start_match:
        return None
    
    start_pos = start_match.end()
    source_from_begin = source[start_pos:]
    
    # Find matching BEGIN/END
    begin_count = 0
    end_count = 0
    pos = 0
    in_string = False
    string_char = None
    
    for i, char in enumerate(source_from_begin):
        # Track string literals
        if char in ("'", '"') and (i == 0 or source_from_begin[i-1] != '\\'):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
        
        # Count BEGIN/END outside of strings
        if not in_string:
            if re.match(r'\bBEGIN\b', source_from_begin[i:], re.IGNORECASE):
                begin_count += 1
            elif re.match(r'\bEND\b', source_from_begin[i:], re.IGNORECASE):
                end_count += 1
                if end_count >= begin_count:
                    # Found matching END
                    body = source_from_begin[:i].strip()
                    return body
    
    return None
