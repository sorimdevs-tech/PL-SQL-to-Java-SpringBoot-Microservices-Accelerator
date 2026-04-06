"""
PL/SQL to Java Logic Converter

Converts extracted PL/SQL logic patterns into proper Java code.
This is the actual translation engine that fixes logical mismatches.
"""
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging

# Import compliance enforcer
try:
    from .java_generation_compliance_enforcer import (
        JavaComplianceEnforcer, 
        enforce_java_compliance
    )
    COMPLIANCE_ENFORCER_AVAILABLE = True
except ImportError:
    COMPLIANCE_ENFORCER_AVAILABLE = False
    logger.warning("Compliance enforcer not available - generated code may not follow all 12 rules")

logger = logging.getLogger(__name__)


@dataclass
class ProcedureSignature:
    """Extracted PL/SQL procedure metadata"""
    name: str
    package: str
    parameters: List[Dict[str, str]]
    return_type: Optional[str]
    body: str
    has_autonomous_transaction: bool = False  # For pragma autonomous_transaction
    

class PLSQLtoJavaConverter:
    """Converts PL/SQL logic to actual Java implementations"""
    
    # PL/SQL to Java type mappings
    TYPE_MAPPINGS = {
        'VARCHAR2': 'String',
        'VARCHAR': 'String',
        'CHAR': 'char',
        'NUMBER': 'BigDecimal',
        'INTEGER': 'int',
        'BINARY_INTEGER': 'int',
        'BOOLEAN': 'boolean',
        'DATE': 'LocalDateTime',
        'TIMESTAMP': 'LocalDateTime',
        'CLOB': 'String',
        'BLOB': 'byte[]',
        'ROWID': 'String',
    }
    
    @staticmethod
    def map_plsql_type_to_java(plsql_type: str) -> str:
        """Map PL/SQL type to Java type"""
        plsql_type = plsql_type.strip().upper()
        
        # Handle parameterized types
        if 'VARCHAR2' in plsql_type:
            return 'String'
        if 'NUMBER' in plsql_type:
            return 'BigDecimal'
        if 'INT' in plsql_type:
            return 'int'
        if 'BOOLEAN' in plsql_type:
            return 'boolean'
        if 'DATE' in plsql_type or 'TIMESTAMP' in plsql_type:
            return 'LocalDateTime'
        
        return PLSQLtoJavaConverter.TYPE_MAPPINGS.get(plsql_type, 'Object')
    
    @staticmethod
    def extract_parameters(body: str) -> List[Dict[str, str]]:
        """Extract procedure parameters from PL/SQL"""
        params = []
        
        # Find parameter section: PROCEDURE name (params) or PROCEDURE name IS
        param_pattern = r'(?:PROCEDURE|FUNCTION)\s+\w+\s*\((.*?)\)\s*(?:RETURN|IS|/)'
        match = re.search(param_pattern, body, re.IGNORECASE | re.DOTALL)
        
        if not match:
            return params
        
        param_section = match.group(1)
        param_lines = [line.strip() for line in param_section.split(',')]
        
        for line in param_lines:
            if not line:
                continue
            
            # Format: name [IN|OUT|IN OUT] type [DEFAULT value]
            param_match = re.match(
                r'(\w+)\s+(?:(IN\s+OUT|IN|OUT)\s+)?(.+?)(?:\s+DEFAULT\s+.+)?$',
                line,
                re.IGNORECASE
            )
            
            if param_match:
                name, direction, ptype = param_match.groups()
                params.append({
                    'name': name.lower(),
                    'direction': direction.upper() if direction else 'IN',
                    'type': ptype.strip(),
                    'java_type': PLSQLtoJavaConverter.map_plsql_type_to_java(ptype.strip()),
                    'java_name': PLSQLtoJavaConverter._to_camel_case(name)
                })
        
        return params
    
    @staticmethod
    def extract_return_type(body: str) -> Optional[str]:
        """Extract function return type from PL/SQL"""
        pattern = r'FUNCTION\s+\w+.*?RETURN\s+(\w+)'
        match = re.search(pattern, body, re.IGNORECASE)
        
        if match:
            return PLSQLtoJavaConverter.map_plsql_type_to_java(match.group(1))
        
        return 'void'
    
    @staticmethod
    def _to_camel_case(name: str) -> str:
        """Convert snake_case to camelCase"""
        parts = [p for p in name.split('_') if p]  # Filter out empty strings
        if not parts:
            return 'value'
        return parts[0].lower() + ''.join(word.capitalize() for word in parts[1:])
    
    @staticmethod
    def _is_java_keyword(name: str) -> bool:
        """Check if name is a Java reserved keyword"""
        java_keywords = {
            'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch', 'char',
            'class', 'const', 'continue', 'default', 'do', 'double', 'else', 'enum',
            'extends', 'final', 'finally', 'float', 'for', 'goto', 'if', 'implements',
            'import', 'instanceof', 'int', 'interface', 'long', 'native', 'new',
            'package', 'private', 'protected', 'public', 'return', 'short', 'static',
            'strictfp', 'super', 'switch', 'synchronized', 'this', 'throw', 'throws',
            'transient', 'try', 'void', 'volatile', 'while', 'true', 'false', 'null'
        }
        return name.lower() in java_keywords
    
    @staticmethod
    def _safe_method_name(name: str) -> str:
        """Ensure method name is not a Java keyword"""
        camel_name = PLSQLtoJavaConverter._to_camel_case(name)
        if PLSQLtoJavaConverter._is_java_keyword(camel_name):
            return camel_name + 'Method'  # e.g., assert -> assertMethod
        return camel_name
    
    @staticmethod
    def _is_balanced_parens(expr: str) -> bool:
        """Check if parentheses are balanced in expression"""
        count = 0
        for char in expr:
            if char == '(':
                count += 1
            elif char == ')':
                count -= 1
            if count < 0:
                return False
        return count == 0
    
    @staticmethod
    def _fix_malformed_expression(expr: str) -> str:
        """
        Fix expressions with unbalanced parentheses by truncating at the point of imbalance.
        Also removes deeply nested function call duplications.
        """
        if not expr:
            return expr
        
        # Check if balanced
        count = 0
        balanced_end = len(expr)
        
        for i, char in enumerate(expr):
            if char == '(':
                count += 1
            elif char == ')':
                count -= 1
            if count < 0:
                balanced_end = i
                break
        
        if count != 0:  # Unbalanced
            expr = expr[:balanced_end]
            # Add closing parens as needed
            expr = expr + ')' * abs(count)
        
        return expr.strip()
    
    @staticmethod
    def _translate_field_access(expr: str) -> str:
        """
        Translate database field access to JavaBean getter pattern.
        Examples:
            customer.customer_id -> customer.getCustomerId()
            invoice.invoice_status -> invoice.getInvoiceStatus()
            p_customer.cust_code -> customer.getCustCode()
        
        NOTE: Skips Java constants (LogConstants.LOG_LEVEL_DEBUG) and class method calls
        """
        # Match patterns like entity.field_name BUT NOT Constants.CONST_NAME or Type.method()
        # Negative lookbehind to exclude common Java classes
        # Fields to translate should be lowercase or snake_case, not ALL_CAPS
        expr = re.sub(
            r'(\w+)\.([a-z_][a-z0-9_]*)\s*(?=[!=<>;\s,\)])',
            lambda m: (
                f"{m.group(1)}.get{PLSQLtoJavaConverter._field_to_getter_name(m.group(2))}()"
                if not (m.group(1) in ('true', 'false', 'null', 'and', 'or', 'not') or m.group(1)[0].isupper())
                else m.group(0)
            ),
            expr,
            flags=re.IGNORECASE
        )
        return expr
    
    @staticmethod
    def _field_to_getter_name(field_name: str) -> str:
        """
        Convert field name to proper JavaBean getter method suffix.
        Examples:
            customer_id -> CustomerId
            cust_code -> CustCode
            status -> Status
        """
        # Convert snake_case to camelCase, then capitalize first letter
        camel = PLSQLtoJavaConverter._to_camel_case(field_name)
        if not camel:
            return 'Value'
        return camel[0].upper() + camel[1:]
    
    @staticmethod
    def translate_validation(condition: str, field: str, message: str) -> str:
        """
        Translate PL/SQL validation to Java.
        Examples:
          IS NULL -> == null
          <= 0 -> <= 0
          NOT IN -> !{ contains }
        """
        java_field = PLSQLtoJavaConverter._to_camel_case(field)
        java_message = message
        # Convert parameter names in message (e.g., p_error_message -> errorMessage)
        java_message = re.sub(
            r'\b([pl])_([a-zA-Z0-9_]+)\b',
            lambda m: PLSQLtoJavaConverter._to_camel_case('_' + m.group(2)),
            java_message,
            flags=re.IGNORECASE
        )
        
        condition_upper = condition.upper().strip()
        
        # IS NULL check
        if 'IS NULL' in condition_upper:
            return f'''if ({java_field} == null) {{
            throw new BusinessException("{java_message}");
        }}'''
        
        # IS NOT NULL check
        if 'IS NOT NULL' in condition_upper:
            return f'''if ({java_field} != null) {{
            throw new BusinessException("{java_message}");
        }}'''
        
        # Simple comparison checks (<=, >=, <, >, ==, !=)
        if any(op in condition_upper for op in ['<=', '>=', '<', '>', '==', '!=', '=']):
            # Replace parameter names with Java names
            java_condition = condition
            java_condition = re.sub(r'\b([pl])_(\w+)', lambda m: PLSQLtoJavaConverter._to_camel_case('_' + m.group(2)), java_condition, flags=re.IGNORECASE)
            return f'''if (!({java_condition})) {{
            throw new BusinessException("{java_message}");
        }}'''
        
        # NVL checks
        if 'NVL' in condition_upper:
            return f"// NVL validation: {condition}"
        
        # Default: wrap condition as negation
        return f'''if (!({condition})) {{
            throw new BusinessException("{message}");
        }}'''
    
    @staticmethod
    def translate_calculation(variable: str, expression: str) -> str:
        """
        Translate PL/SQL calculation to Java.
        Examples:
          v_total = p_amount * 1.15
          l_vat = nvl(p_amount, 0) * vat_rate / 100

        FIX: amount * rate / 100 VAT-style formulas are emitted as BigDecimal
        multiply/divide chains so monetary precision is preserved.
        """
        java_var = PLSQLtoJavaConverter._to_camel_case(variable)
        java_expr = expression

        # Replace parameter prefixes (p_, l_) with camelCase
        java_expr = re.sub(
            r'\b[pl]_(\w+)',
            lambda m: PLSQLtoJavaConverter._to_camel_case('_' + m.group(1)),
            java_expr, flags=re.IGNORECASE
        )

        # Replace PL/SQL functions with Java equivalents
        java_expr = re.sub(r'\bNVL\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)', r'(\1 != null ? \1 : \2)', java_expr, flags=re.IGNORECASE)
        java_expr = re.sub(r'\bTRUNC\s*\(\s*(\w+)\s*\)', r'Math.floor(\1)', java_expr, flags=re.IGNORECASE)
        java_expr = re.sub(r'\bROUND\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)', r'Math.round(\1 * Math.pow(10, \2)) / Math.pow(10, \2)', java_expr, flags=re.IGNORECASE)

        # FIX: VAT-style formula  <amount> * <rate> / 100
        # Rewrite to BigDecimal.multiply().divide() so no precision is lost.
        # Matches any:  expr * expr / 100   (the /100 is the discriminating marker)
        vat_pattern = re.compile(
            r'(\w[\w.()]*)\s*\*\s*(\w[\w.()]*)\s*/\s*100\b',
            re.IGNORECASE
        )
        def _vat_to_bigdecimal(m: re.Match) -> str:
            a, b = m.group(1).strip(), m.group(2).strip()
            return (
                f'{a}.multiply({b})'
                f'.divide(java.math.BigDecimal.valueOf(100), 2, java.math.RoundingMode.HALF_UP)'
            )
        java_expr = vat_pattern.sub(_vat_to_bigdecimal, java_expr)

        return f"BigDecimal {java_var} = {java_expr};"
    
    @staticmethod
    def translate_insert(table: str, columns: List[str], values: List[str]) -> str:
        """
        Translate PL/SQL INSERT to Java repository call.
        """
        entity_name = PLSQLtoJavaConverter._table_to_entity(table)
        
        # Build save call
        java_code = f"{entity_name} entity = new {entity_name}();\n"
        
        for col, val in zip(columns, values):
            # Generate proper setter name (capitalize first letter after camelCase)
            col_name = PLSQLtoJavaConverter._to_camel_case(col)
            setter_name = 'set' + col_name[0].upper() + col_name[1:] if len(col_name) > 0 else 'set'
            
            # Translate the value expression (handles SUBSTR, functions, etc.)
            val_clean = PLSQLtoJavaConverter._translate_plsql_expression(val)
            
            java_code += f"entity.{setter_name}({val_clean});\n"
        
        repo_name = PLSQLtoJavaConverter._entity_to_repository_name(entity_name)
        java_code += f"{repo_name}.save(entity);"
        
        return java_code
    
    @staticmethod
    def _translate_plsql_expression(expr: str) -> str:
        """
        Translate PL/SQL expressions to Java with proper operator conversion.
        
        CRITICAL: Parameter name conversion happens LAST after all function translations.
        This ensures SUBSTR(p_text, 1, 255) becomes text.substring() not pText.substring().
        
        Examples:
            p_customer_id IS NOT NULL -> customerId != null
            p_amount > 0 -> amount > 0 
            NVL(p_value, 0) -> (value != null ? value : 0)
            customer_pkg.c_status_active -> "ACTIVE" (placeholder for status constant)
            p_param => value -> p_param = value (named parameter)
        """
        if not expr:
            return expr
        
        # =========== STEP 1: Core operator translations (no param conversion) ===========
        
        # CRITICAL ORDER: Handle IS NULL operators FIRST before other replacements
        # IS NOT NULL -> != null
        expr = re.sub(r'\s+IS\s+NOT\s+NULL\b', ' != null', expr, flags=re.IGNORECASE)
        # IS NULL -> == null
        expr = re.sub(r'\s+IS\s+NULL\b', ' == null', expr, flags=re.IGNORECASE)
        
        # Translate NOT operator to Java ! operator
        # Must NOT replace NOT in NOT IN or NOT LIKE patterns (handle those separately if needed)
        expr = re.sub(r'\bNOT\s+\(', '!(', expr, flags=re.IGNORECASE)
        expr = re.sub(r'\bNOT\s+([A-Za-z_])', r'!\1', expr, flags=re.IGNORECASE)
        
        # Translate named parameters (=>) to Java assignment (=) BUT preserve == operators
        # First, protect == by replacing with a placeholder
        expr = expr.replace('==', '\x00DOUBLE_EQ\x00')
        # Now translate =>
        expr = expr.replace('=>', '=')
        # Restore == operators
        expr = expr.replace('\x00DOUBLE_EQ\x00', '==')
        
        # =========== STEP 2: Function translations (before param name conversion) ===========
        
        # Translate COALESCE function (preserve original param names)
        expr = re.sub(
            r'(?i)COALESCE\s*\(\s*([^)]+)\s*\)',
            lambda m: PLSQLtoJavaConverter._translate_coalesce(m.group(1)),
            expr
        )
        
        # Translate NVL function: NVL(value, default) -> (value != null ? value : default)
        # CRITICAL: Do NOT convert param names here, keep them as is
        expr = re.sub(
            r'(?i)NVL\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)',
            r'(\1 != null ? \1 : \2)',
            expr
        )
        
        # Translate SUBSTR(str, start, length) -> str.substring(start-1, start-1+length)
        # CRITICAL: Extract variable name WITHOUT the p_ prefix before camelCase conversion
        def translate_substr(m):
            var_name = m.group(1)  # Keep original: p_text, p_amount, etc.
            start = int(m.group(2))
            length = int(m.group(3))
            end = start - 1 + length
            return f'{var_name}.substring({start-1}, {end})'
        
        expr = re.sub(
            r'(?i)SUBSTR\s*\(\s*([a-zA-Z_]\w*)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)',
            translate_substr,
            expr
        )
        
        # TRUNC(x) -> Math.floor(x)
        expr = re.sub(r'(?i)TRUNC\s*\(\s*([^)]+)\s*\)', r'Math.floor(\1)', expr)
        
        # ROUND(x, n) -> Math.round formula
        expr = re.sub(
            r'(?i)ROUND\s*\(\s*([^,]+)\s*,\s*(\d+)\s*\)',
            r'Math.round(\1 * Math.pow(10, \2)) / Math.pow(10, \2)',
            expr
        )
        
        # LENGTH(string) -> string.length()
        expr = re.sub(r'(?i)LENGTH\s*\(\s*([^)]+)\s*\)', r'\1.length()', expr)
        
        # UPPER(string) -> string.toUpperCase()
        expr = re.sub(r'(?i)UPPER\s*\(\s*([^)]+)\s*\)', r'\1.toUpperCase()', expr)
        
        # LOWER(string) -> string.toLowerCase()
        expr = re.sub(r'(?i)LOWER\s*\(\s*([^)]+)\s*\)', r'\1.toLowerCase()', expr)
        
        # SYSDATE -> LocalDateTime.now() (current timestamp)
        expr = re.sub(r'\bSYSDATE\b', 'LocalDateTime.now()', expr, flags=re.IGNORECASE)

        # =========== CASE WHEN → Java ternary chain ===========
        # Handles: CASE x WHEN v1 THEN r1 WHEN v2 THEN r2 ELSE rN END
        # and:     CASE WHEN cond1 THEN r1 WHEN cond2 THEN r2 ELSE rN END
        def _translate_case_when(m: re.Match) -> str:
            """Convert a PL/SQL CASE expression to nested Java ternaries."""
            inner = m.group(1).strip()

            # Detect "simple CASE x WHEN …" vs "searched CASE WHEN …"
            simple_match = re.match(r'^(.+?)\s+WHEN\b', inner, re.IGNORECASE)
            searched = re.match(r'^WHEN\b', inner, re.IGNORECASE)

            # Split on WHEN / THEN / ELSE tokens respecting nesting
            tokens = re.split(r'\b(WHEN|THEN|ELSE)\b', inner, flags=re.IGNORECASE)

            branches = []  # list of (condition_expr, result_expr)
            else_expr = 'null'
            i = 0
            # For simple CASE, the subject is the first token before the first WHEN
            subject = ''
            if not searched and simple_match:
                subject_raw = simple_match.group(1).strip()
                # Remove it from the front before we parse tokens
                inner_rest = inner[len(subject_raw):].strip()
                tokens = re.split(r'\b(WHEN|THEN|ELSE)\b', inner_rest, flags=re.IGNORECASE)
                subject = PLSQLtoJavaConverter._translate_plsql_expression(subject_raw)

            i = 0
            while i < len(tokens):
                tok = tokens[i].strip().upper()
                if tok == 'WHEN' and i + 2 < len(tokens):
                    cond_raw = tokens[i + 1].strip() if i + 1 < len(tokens) else ''
                    then_kw = tokens[i + 2].strip().upper() if i + 2 < len(tokens) else ''
                    result_raw = tokens[i + 3].strip() if i + 3 < len(tokens) else ''
                    if then_kw == 'THEN':
                        if subject:
                            # simple case: subject == cond_raw
                            cond_java = f'{subject} == {PLSQLtoJavaConverter._translate_plsql_expression(cond_raw)}'
                        else:
                            cond_java = PLSQLtoJavaConverter._translate_plsql_expression(cond_raw)
                        result_java = PLSQLtoJavaConverter._translate_plsql_expression(result_raw)
                        branches.append((cond_java, result_java))
                        i += 4
                        continue
                elif tok == 'ELSE' and i + 1 < len(tokens):
                    else_expr = PLSQLtoJavaConverter._translate_plsql_expression(tokens[i + 1].strip())
                    i += 2
                    continue
                i += 1

            if not branches:
                return expr  # Could not parse – return unchanged

            # Build nested ternary right-to-left
            result = else_expr
            for cond, val in reversed(branches):
                result = f'({cond} ? {val} : {result})'
            return result

        # Apply CASE…END translation (non-greedy, innermost first via loop)
        prev = None
        while prev != expr:
            prev = expr
            expr = re.sub(
                r'\bCASE\b\s+(.*?)\s*\bEND\b',
                _translate_case_when,
                expr,
                flags=re.IGNORECASE | re.DOTALL
            )

        # =========== STEP 3: Constants and package references ===========
        
        # Translate standalone constants (c_xxx to Java constant)
        # E.g., c_log_level_debug -> LogConstants.LOG_LEVEL_DEBUG
        expr = re.sub(
            r'\bc_([a-zA-Z0-9_]+)\b',
            lambda m: f'LogConstants.{m.group(1).upper()}',
            expr,
            flags=re.IGNORECASE
        )
        
        # Translate PL/SQL package constants to string placeholders
        # E.g., invoice_pkg.c_type_standard -> "STANDARD"
        expr = re.sub(
            r'(\w+_pkg)\.c_(\w+)',
            lambda m: f'"{m.group(2).upper()}"',
            expr,
            flags=re.IGNORECASE
        )
        
        # Translate package.function(...) calls to service calls
        # E.g., customer_pkg.get_customer(p_id) -> customerService.getCustomer(id)
        expr = re.sub(
            r'(\w+_pkg)\.(\w+)\s*\(',
            lambda m: f'{PLSQLtoJavaConverter._service_for_package(m.group(1))}.{PLSQLtoJavaConverter._to_camel_case(m.group(2))}(',
            expr,
            flags=re.IGNORECASE
        )
        
        # NULL -> null
        expr = re.sub(r'(?i)\bNULL\b', 'null', expr)
        
        # TRUE/FALSE -> true/false
        expr = re.sub(r'(?i)\bTRUE\b', 'true', expr)
        expr = re.sub(r'(?i)\bFALSE\b', 'false', expr)
        
        # := (PL/SQL assignment) -> = (Java assignment), protect == again
        expr = expr.replace('==', '\x00DOUBLE_EQ\x00')
        expr = expr.replace(':=', '=')
        expr = expr.replace('\x00DOUBLE_EQ\x00', '==')
        
        # || (PL/SQL concatenation) -> + (Java concatenation)
        expr = expr.replace('||', ' + ')
        
        # =========== STEP 4: Parameter name conversion (LAST!) ===========
        
        # Convert variable names p_ and l_ to camelCase
        # Must happen AFTER all function translations so p_text stays as p_text in SUBSTR
        expr = re.sub(
            r'\b([pl])_([a-zA-Z0-9_]+)\b',
            lambda m: PLSQLtoJavaConverter._to_camel_case('_' + m.group(2)),
            expr,
            flags=re.IGNORECASE
        )
        
        # Translate field access patterns to JavaBean getters (e.g., entity.field_name -> entity.getFieldName())
        expr = PLSQLtoJavaConverter._translate_field_access(expr)
        
        # Fix malformed expressions with unbalanced parentheses
        if not PLSQLtoJavaConverter._is_balanced_parens(expr):
            expr = PLSQLtoJavaConverter._fix_malformed_expression(expr)
        
        return expr
    
    @staticmethod
    def _service_for_package(pkg_name: str) -> str:
        """Map PL/SQL package name to Java service name"""
        pkg_lower = pkg_name.lower()
        mapping = {
            'customer_pkg': 'customerService',
            'invoice_pkg': 'invoiceService',
            'invoice_api_pkg': 'invoiceApiService',
            'paypal_util_pkg': 'paypalService',
            'xtp': 'xtpBufferService',
            'appl_error_pkg': 'errorService',
            'appl_log_pkg': 'logService',
        }
        return mapping.get(pkg_lower, f'{PLSQLtoJavaConverter._to_camel_case(pkg_lower)}Service')
    
    @staticmethod
    def _translate_coalesce(args_str: str) -> str:
        """
        Translate COALESCE(a, b, c) to nested ternary: (a != null ? a : b != null ? b : c)
        """
        args = [arg.strip() for arg in args_str.split(',')]
        if not args:
            return 'null'
        if len(args) == 1:
            return args[0]
        
        result = args[-1]
        for i in range(len(args) - 2, -1, -1):
            result = f'({args[i]} != null ? {args[i]} : {result})'
        return result
    
    @staticmethod
    def translate_update(table: str, assignments: Dict[str, str], where_clause: str) -> str:
        """
        Translate PL/SQL UPDATE to Java repository call.
        """
        entity_name = PLSQLtoJavaConverter._table_to_entity(table)
        repo_name = PLSQLtoJavaConverter._entity_to_repository_name(entity_name)
        
        java_code = f"// UPDATE {table}\n"
        java_code += f"{entity_name} existing = {repo_name}.find...();\n"
        
        for col, val in assignments.items():
            setter = PLSQLtoJavaConverter._to_camel_case(col)
            val_clean = PLSQLtoJavaConverter._to_camel_case(val.lstrip('p_lv'))
            java_code += f"existing.set{setter.capitalize()}({val_clean});\n"
        
        java_code += f"{repo_name}.save(existing);"
        
        return java_code
    
    @staticmethod
    def _infer_parameter_type(param_name: str) -> str:
        """
        Infer Java type from PL/SQL parameter name patterns.
        Enhanced to handle collections, Optional, and complex types.
        
        Examples:
            id, customer_id -> Long
            amount, rate, price, vat -> BigDecimal
            date, time, timestamp -> LocalDateTime
            flag, is_*, enabled -> boolean
            customers, statuses, *_list, *_ids -> List<Type>
            page_*, optional_* -> Page<Type> or Optional<Type>
            *_map -> Map<String, Type>
        """
        name_lower = param_name.lower()
        
        # Check for collection types first (plural, list, etc.)
        if any(name_lower.endswith(suffix) for suffix in ['s', '_list', '_ids', '_codes', '_values']):
            # Determine collection type
            if '_map' in param_name:
                # Map type
                base_type = PLSQLtoJavaConverter._infer_base_type(param_name.replace('_map', ''))
                return f'Map<String, {base_type}>'
            elif 'page' in name_lower:
                # Pagination type
                base_type = PLSQLtoJavaConverter._infer_base_type(param_name.replace('page_', '').replace('_page', ''))
                return f'Page<{base_type}>'
            else:
                # List type
                base_type = PLSQLtoJavaConverter._infer_base_type(param_name.rstrip('s'))
                if base_type != 'String':
                    return f'List<{base_type}>'
                # If plural of string param, still List
                return 'List<String>'
        
        # Check for Optional types
        if 'optional' in name_lower:
            base_type = PLSQLtoJavaConverter._infer_base_type(param_name.replace('optional_', ''))
            return f'Optional<{base_type}>'
        
        # Check for Page/pagination types
        if 'page' in name_lower and 'size' not in name_lower:
            base_type = PLSQLtoJavaConverter._infer_base_type(param_name.replace('page_', '').replace('_page', ''))
            return f'Page<{base_type}>'
        
        # Check for Map types
        if 'map' in name_lower:
            base_type = PLSQLtoJavaConverter._infer_base_type(param_name.replace('_map', ''))
            return f'Map<String, {base_type}>'
        
        # Fallback to base type inference (for non-collection)
        return PLSQLtoJavaConverter._infer_base_type(param_name)
    
    @staticmethod
    def _infer_base_type(param_name: str) -> str:
        """
        Infer base Java type (non-collection) from parameter name.
        Used as fallback in _infer_parameter_type.
        """
        name_lower = param_name.lower()
        
        if 'id' in name_lower or 'pk' in name_lower or 'seq' in name_lower:
            return 'Long'
        elif 'amount' in name_lower or 'rate' in name_lower or 'price' in name_lower or 'total' in name_lower or 'vat' in name_lower or 'balance' in name_lower or 'value' in name_lower:
            return 'BigDecimal'
        elif 'date' in name_lower or 'time' in name_lower or 'timestamp' in name_lower:
            return 'LocalDateTime'
        elif 'flag' in name_lower or 'is_' in name_lower or 'enabled' in name_lower or 'active' in name_lower:
            return 'boolean'
        elif 'count' in name_lower or 'size' in name_lower or 'quantity' in name_lower or 'number' in name_lower:
            return 'Integer'
        elif 'page' in name_lower and 'size' in name_lower:
            return 'Integer'
        
        return 'String'  # Default for text parameters
    
    @staticmethod
    def _infer_return_type(package: str, function: str) -> str:
        """
        Infer return type from PL/SQL function name patterns.
        
        Examples:
            get_all_customers -> List<Customer>
            count_* -> Integer
            get_* -> depends on name (Long for id, BigDecimal for amount, etc.)
            build_*_map -> Map<String, Object>
            get_*_paged -> Page<Object>
        """
        func_lower = function.lower()
        pkg_lower = package.lower()
        
        # Pagination return types
        if 'paged' in func_lower or 'page_' in func_lower:
            return 'Page<Object>'
        
        # Count methods return Integer
        if func_lower.startswith('count'):
            return 'Integer'
        
        # Map building methods
        if 'build' in func_lower and 'map' in func_lower:
            return 'Map<String, Object>'
        
        # List/collection return types
        if 'get_all' in func_lower or func_lower.endswith('s'):
            # Determine base entity type from package
            if 'customer' in pkg_lower:
                return 'List<Customer>'
            elif 'invoice' in pkg_lower:
                return 'List<Invoice>'
            else:
                return 'List<Object>'
        
        # Single entity return types
        if 'get' in func_lower:
            if 'amount' in func_lower or 'price' in func_lower or 'vat' in func_lower:
                return 'BigDecimal'
            elif 'count' in func_lower:
                return 'Integer'
            elif 'customer' in pkg_lower:
                return 'Customer'
            elif 'invoice' in pkg_lower:
                return 'Invoice'
            else:
                return 'Object'
        
        # Default based on function intent
        if 'create' in func_lower or 'new' in func_lower or 'insert' in func_lower:
            if 'customer' in pkg_lower:
                return 'Long'  # Returns new ID
            elif 'invoice' in pkg_lower:
                return 'Long'
            else:
                return 'Object'
        
        return 'Object'  # Default return type
    
    @staticmethod
    def _translate_package_call(package: str, function: str, params: str) -> Optional[str]:
        """
        Translate PL/SQL package function calls to Java service/repository calls.
        Returns actual method calls, not comments.
        
        Examples:
            customer_pkg.get_customer(p_id) => customerService.getCustomer(id)
            invoice_pkg.new_invoice(...) => invoiceService.newInvoice(...)
        """
        func_name = PLSQLtoJavaConverter._to_camel_case(function)
        params_translated = PLSQLtoJavaConverter._translate_plsql_expression(params)
        
        if 'customer_pkg' in package.lower():
            return f"customerService.{func_name}({params_translated})"
        elif 'invoice_pkg' in package.lower():
            return f"invoiceService.{func_name}({params_translated})"
        elif 'appl_log_pkg' in package.lower():
            return None  # Logging handled separately
        elif 'paypal' in package.lower():
            return f"paypalService.{func_name}({params_translated})"
        elif 'xtp' in package.lower():
            return f"xtpBufferService.{func_name}({params_translated})"
        
        return f"// {package}.{func_name}({params_translated})"
    
    @staticmethod
    def translate_commit() -> str:
        """Add @Transactional annotation"""
        return "@Transactional"
    
    @staticmethod
    def translate_exception_raise(error_code: str, message: str) -> str:
        """
        Translate PL/SQL RAISE_APPLICATION_ERROR to Java.
        Example: RAISE_APPLICATION_ERROR(-20000, 'error') -> throw new BusinessException(...)
        """
        return f'throw new BusinessException("{message}");'
    
    @staticmethod
    def _table_to_entity(table_name: str) -> str:
        """Convert table name to entity class name"""
        parts = table_name.split('_')
        return ''.join(word.capitalize() for word in parts) + 'Entity'
    
    @staticmethod
    def _entity_to_repository_name(entity_name: str) -> str:
        """Convert entity name to repository variable name (camelCase)"""
        # Remove 'Entity' suffix if present
        if entity_name.endswith('Entity'):
            entity_name = entity_name[:-6]
        # Convert PascalCase to camelCase
        if entity_name:
            return entity_name[0].lower() + entity_name[1:] + 'Repository'
        return 'repository'
    
    @staticmethod
    def _table_to_repository_name(table_name: str) -> str:
        """Convert table name directly to repository variable name (camelCase)"""
        entity_name = PLSQLtoJavaConverter._table_to_entity(table_name)
        return PLSQLtoJavaConverter._entity_to_repository_name(entity_name)
    
    @staticmethod
    def _plsql_type_to_java(plsql_type: str, table_context: str = None) -> str:
        """
        Convert PL/SQL type to corresponding Java type.
        
        FIX (Bug 1 – %ROWTYPE mapped to Object):
            When a parameter or return type is table%ROWTYPE the table name is
            sitting right in the type string.  We extract it and convert it to the
            proper JPA entity class name so the generated Java is type-safe.
        
        Examples:
            NUMBER -> Long or BigDecimal
            VARCHAR2 -> String
            DATE -> LocalDate
            TIMESTAMP -> LocalDateTime
            xy_customer%ROWTYPE -> XyCustomerEntity   ← was wrongly 'Object'
        """
        plsql_type_upper = plsql_type.upper().strip()
        
        # FIX: Handle %ROWTYPE by extracting the table name and producing the entity type.
        # Input looks like  "XY_CUSTOMER%ROWTYPE"  or  "xy_customer%rowtype".
        if '%ROWTYPE' in plsql_type_upper:
            # Extract the table part that precedes the %ROWTYPE qualifier.
            table_name = plsql_type_upper.split('%')[0].strip()
            if table_name:
                # Convert table name to PascalCase entity (e.g. XY_CUSTOMER -> XyCustomerEntity)
                entity_name = PLSQLtoJavaConverter._table_to_entity(table_name.lower())
                return entity_name  # e.g. XyCustomerEntity
            # If there is no table prefix (bare %ROWTYPE), fall back to caller-supplied context.
            if table_context:
                return PLSQLtoJavaConverter._table_to_entity(table_context.lower())
            return 'Object'  # Last-resort fallback
        
        # Numeric types
        if plsql_type_upper in ['NUMBER', 'INTEGER', 'INT', 'PLS_INTEGER']:
            return 'Long'
        if plsql_type_upper in ['NUMBER(*,2)', 'DECIMAL', 'NUMERIC']:
            return 'BigDecimal'
        if plsql_type_upper in ['FLOAT', 'BINARY_FLOAT']:
            return 'Float'
        if plsql_type_upper in ['DOUBLE', 'BINARY_DOUBLE']:
            return 'Double'
        
        # String types
        if plsql_type_upper.startswith('VARCHAR') or plsql_type_upper.startswith('CHAR') or plsql_type_upper.startswith('TEXT'):
            return 'String'
        
        # Date/Time types
        if plsql_type_upper in ['DATE']:
            return 'LocalDate'
        if plsql_type_upper in ['TIMESTAMP', 'TIMESTAMP WITH TIME ZONE', 'TIMESTAMP WITH LOCAL TIME ZONE']:
            return 'LocalDateTime'
        if plsql_type_upper.startswith('INTERVAL'):
            return 'Duration'
        
        # Boolean types
        if plsql_type_upper in ['BOOLEAN']:
            return 'Boolean'
        
        # LOB types
        if plsql_type_upper in ['CLOB', 'NCLOB']:
            return 'String'  # Simplified: use String instead of Clob
        if plsql_type_upper in ['BLOB']:
            return 'byte[]'
        
        # Default to Object for unknown types
        return 'Object'
    
    @staticmethod
    def generate_method_signature(proc: 'ProcedureSignature') -> str:
        """
        Generate proper Java method signature from PL/SQL procedure.
        """
        method_name = PLSQLtoJavaConverter._to_camel_case(proc.name)
        return_type = proc.return_type or 'void'
        
        # Build parameter list - ONLY input parameters become method params
        params = []
        for p in proc.parameters:
            if p['direction'] != 'OUT':  # Skip OUT-only params
                params.append(f"{p['java_type']} {p['java_name']}")
        
        params_str = ', '.join(params) if params else ''
        
        return f"public {return_type} {method_name}({params_str})"
    
    @staticmethod
    def generate_java_method(
        proc_name: str,
        logic: 'ExtractedLogic',
        entity_names: Dict[str, str] = None,
        package_name: str = 'com.example.demo'
    ) -> str:
        """
        Generate complete Java method implementation from PL/SQL logic.
        Properly translates expressions and generates real Java code.
        
        Args:
            proc_name: Procedure name (for method naming)
            logic: Extracted logic patterns
            entity_names: Mapping of table names to entity classes
            package_name: Java package name
        
        Returns:
            Complete Java method code with proper syntax
        """
        if entity_names is None:
            entity_names = {}
        
        method_name = PLSQLtoJavaConverter._safe_method_name(proc_name)
        
        # Determine return type based on logic
        # Priority: extracted return_type from signature > inferred from logic > default void
        return_type = 'void'
        
        # First, check if return type was explicitly extracted from signature
        if logic.return_type:
            plsql_type = logic.return_type.upper()
            # _plsql_type_to_java now handles %ROWTYPE correctly by extracting the
            # table name and converting it to the proper JPA entity class name.
            return_type = PLSQLtoJavaConverter._plsql_type_to_java(plsql_type)
        # If no explicit return type but there are RETURN statements, infer from logic
        elif logic.returns:
            if logic.inserts:
                # Check if INSERT has RETURNING clause
                for insert in logic.inserts:
                    if insert.get('returning_column'):
                        return_type = 'Long'  # Returning column ID
                        break
            
            if return_type == 'void' and logic.selects:
                # SELECT statements return rows/records
                if logic.return_type and '%rowtype' in logic.return_type.lower():
                    return_type = 'Object'
                else:
                    return_type = 'Object'
        
        # Extract method parameters from multiple sources
        params_dict = {}
        
        # Helper to convert PL/SQL parameter names to Java
        def plsql_param_to_java_name(param_name: str) -> str:
            """Convert p_xxx or l_xxx style names to camelCase java names"""
            # Remove p_, l_, or v_ prefix if present
            if param_name and param_name[0] in ['p', 'l', 'v'] and len(param_name) > 1 and param_name[1] == '_':
                param_name = param_name[2:]  # Remove the prefix
            # Convert to camelCase
            return PLSQLtoJavaConverter._to_camel_case(param_name)
        
        # 1. From procedure signature (procedure_parameters)
        for param in logic.procedure_parameters:
            if param.get('direction') in ['IN', 'IN_OUT']:  # Only IN parameters become method params
                param_name = param.get('name', '')
                camel_name = plsql_param_to_java_name(param_name)
                param_type = PLSQLtoJavaConverter._plsql_type_to_java(param.get('plsql_type', 'VARCHAR2'))
                if camel_name not in params_dict:
                    params_dict[camel_name] = f"{param_type} {camel_name}"
        
        # 2. From error assertions (input validations) - adds any missing parameters
        for assertion in logic.error_assertions:
            cond = assertion.get('condition', '')
            # Extract p_parameter_name patterns
            for match in re.finditer(r'\bp_([a-zA-Z0-9_]+)\b', cond):
                param_name = match.group(0)  # Get full p_xxx
                camel_name = plsql_param_to_java_name(param_name)
                param_type = PLSQLtoJavaConverter._infer_parameter_type(param_name)
                if camel_name not in params_dict:
                    params_dict[camel_name] = f"{param_type} {camel_name}"
        
        # Convert params_dict to params_str for method signature
        params_str = ', '.join(params_dict.values())
        
        # Build method body
        body_lines = []
        
        # 1. VALIDATION LAYER - error assertions and validations
        if logic.validations or logic.error_assertions:
            body_lines.append("    // === Validation Layer ===")
            
            # Handle structured validations from IF...THEN...RAISE
            for validation in logic.validations:
                condition = validation.get('condition', 'true')
                error_code = validation.get('error_code', '20000')
                message = validation.get('message', 'Validation failed')
                
                # Translate condition to proper Java
                condition_java = PLSQLtoJavaConverter._translate_plsql_expression(condition)
                
                # Check if message is a parameter reference (p_xxx, l_xxx, v_xxx)
                if message and re.match(r'^[plv]_\w+$', message, re.IGNORECASE):
                    # Extract just the parameter name without the prefix for camelCase conversion
                    # p_error_message -> errorMessage
                    if message[1] == '_':
                        param_part = message[2:]  # Remove p_, l_, or v_
                        message_java = PLSQLtoJavaConverter._to_camel_case(param_part)
                    else:
                        message_java = PLSQLtoJavaConverter._to_camel_case(message)
                    body_lines.append(f"    if ({condition_java}) {{")
                    body_lines.append(f'        throw new BusinessException("-{error_code}", {message_java});')
                    body_lines.append("    }")
                else:
                    body_lines.append(f"    if ({condition_java}) {{")
                    body_lines.append(f'        throw new BusinessException("-{error_code}", "{message}");')
                    body_lines.append("    }")
            
            # Handle error_assertions (package.assert style)
            for assertion in logic.error_assertions:
                condition = assertion.get('condition', 'true')
                message = assertion.get('message', 'Validation failed')
                
                # Translate condition to proper Java
                java_condition = PLSQLtoJavaConverter._translate_plsql_expression(condition)
                
                # CRITICAL: assert(condition, message) in PL/SQL does:
                # IF NOT NVL(condition, false) THEN RAISE...
                # So in Java we need: IF !(condition) { throw ... }
                # Wrap with NOT to match assert semantics
                java_condition = f"!({java_condition})"
                
                # Check if message is a parameter reference (p_xxx, l_xxx, v_xxx)
                if message and re.match(r'^[plv]_\w+$', message, re.IGNORECASE):
                    # Extract just the parameter name without the prefix for camelCase conversion
                    # p_error_message -> errorMessage
                    if message[1] == '_':
                        param_part = message[2:]  # Remove p_, l_, or v_
                        message_var = PLSQLtoJavaConverter._to_camel_case(param_part)
                    else:
                        message_var = PLSQLtoJavaConverter._to_camel_case(message)
                    body_lines.append(f"    if ({java_condition}) {{")
                    body_lines.append(f'        throw new BusinessException({message_var});')
                    body_lines.append("    }")
                else:
                    body_lines.append(f"    if ({java_condition}) {{")
                    body_lines.append(f'        throw new BusinessException("{message}");')
                    body_lines.append("    }")
        
        # 2. DERIVED VALUES LAYER
        declared_vars = set()  # Track which variables have been declared to avoid duplicates
        
        if logic.derived_values or logic.function_calls or logic.calculations:
            body_lines.append("    // === Derived Values Layer ===")
            
            # Variable assignments from calculations
            for calc in logic.calculations:
                var_name = PLSQLtoJavaConverter._to_camel_case(calc.get('variable', ''))
                if var_name in declared_vars:
                    continue
                expr = calc.get('expression', '')
                # Strip assignment operator from expression
                expr = expr.lstrip(':= ')
                java_expr = PLSQLtoJavaConverter._translate_plsql_expression(expr)
                if java_expr.strip() and not java_expr.strip().startswith('//'):
                    body_lines.append(f"    var {var_name} = {java_expr};")
                    declared_vars.add(var_name)
            
            # Derived values from coalesce, case, nvl, etc.
            for dv in logic.derived_values:
                var_name = PLSQLtoJavaConverter._to_camel_case(dv.get('variable', ''))
                if var_name in declared_vars:
                    continue
                expr = dv.get('expression', '')
                # Strip assignment operator from expression
                expr = expr.replace(':=', '').strip()
                # Remove the leading 'l_variable :=' if present, leaving just the COALESCE/NVL part
                if 'COALESCE' not in expr.upper() and 'NVL' not in expr.upper():
                    # If it doesn't contain function, skip or handle as calculation
                    continue
                java_expr = PLSQLtoJavaConverter._translate_plsql_expression(expr)
                if java_expr.strip() and not java_expr.strip().startswith('//'):
                    body_lines.append(f"    var {var_name} = {java_expr};")
                    declared_vars.add(var_name)
            
            # Function calls to fetch related data (skip assert/log calls, handle data fetch calls)
            for fc in logic.function_calls:
                pkg = fc.get('package', '').lower()
                func = fc.get('function', '').lower()
                params_fc = fc.get('params', '')
                
                # Skip assertion and logging function calls (handled in validation/logging layers)
                if 'assert' in func or 'log' in func:
                    continue
                
                func_name = PLSQLtoJavaConverter._to_camel_case(fc.get('function', ''))
                result_var_name = f'{func_name}Result'
                
                # Skip if we've already declared this variable
                if result_var_name in declared_vars:
                    continue
                
                params_java = PLSQLtoJavaConverter._translate_plsql_expression(params_fc)
                
                # Generate service call only for actual data-fetching functions
                if 'customer' in pkg and 'get' in func:
                    body_lines.append(f"    var {result_var_name} = customerService.{func_name}({params_java});")
                    declared_vars.add(result_var_name)
                elif 'invoice' in pkg and 'get' in func:
                    body_lines.append(f"    var {result_var_name} = invoiceService.{func_name}({params_java});")
                    declared_vars.add(result_var_name)
        
        # 3. LOGGING LAYER
        if logic.logging_calls:
            body_lines.append("    // === Logging ===")
            for log_call in logic.logging_calls:
                message = log_call.get('message', '')
                body_lines.append(f'    logger.info("{message}");')
        
        # 4. DATABASE OPERATIONS LAYER
        if logic.inserts or logic.updates or logic.deletes or logic.selects:
            body_lines.append("    // === Database Operations ===")
            
            # Handle SELECTs (fetch before modify)  
            for select in logic.selects:
                table = select.get('table', '')
                where_clause = select.get('where', '')
                columns = select.get('columns', '*')
                into_vars = select.get('into_variables', '')
                entity_name = PLSQLtoJavaConverter._table_to_entity(table)
                # Convert repository variable name properly (e.g., XyCustomerEntity -> xyCustomerRepository)
                repo_name = PLSQLtoJavaConverter._table_to_repository_name(table)
                var_name = PLSQLtoJavaConverter._to_camel_case(into_vars)
                has_exception = select.get('has_exception', False)
                
                if where_clause and where_clause.strip().lower() != 'true':
                    java_where = PLSQLtoJavaConverter._translate_plsql_expression(where_clause)
                    
                    # Clean up the where clause to extract the actual parameter
                    # E.g., "customer_id = p_customer_id" -> extract "customerId" 
                    # Use a simpler approach: look for "= p_parameter_name" or "= l_variable"
                    id_match = re.search(r'=\s*([pl]_\w+)\b', java_where, re.IGNORECASE)
                    if id_match:
                        id_param = id_match.group(1)
                        id_param_camel = PLSQLtoJavaConverter._to_camel_case(id_param)
                        body_lines.append(f"    Optional<{entity_name}> {var_name}Opt = {repo_name}.findById({id_param_camel});")
                        if has_exception:
                            body_lines.append(f"    var {var_name} = {var_name}Opt.orElse(null);")
                        else:
                            body_lines.append(f"    var {var_name} = {var_name}Opt.orElse(null);")
                    else:
                        # Fallback for complex WHERE clauses
                        body_lines.append(f"    var {var_name} = {repo_name}.findOne({java_where}).orElse(null);")
                    
                    declared_vars.add(var_name)
            
            # Handle INSERTs
            for insert in logic.inserts:
                if insert.get('is_record_insert'):
                    # INSERT INTO table VALUES record (for %rowtype)
                    table = insert.get('table', '')
                    record_var = insert.get('record_value', '')
                    entity_name = PLSQLtoJavaConverter._table_to_entity(table)
                    repo_name = PLSQLtoJavaConverter._table_to_repository_name(table)
                    
                    # Assume the record is already of entity type
                    if insert.get('returning_column'):
                        returning_var = PLSQLtoJavaConverter._to_camel_case(insert.get('returning_into', 'resultId'))
                        body_lines.append(f"    Long {returning_var} = {repo_name}.save({record_var}).getId();")
                        if returning_var not in declared_vars:
                            declared_vars.add(returning_var)
                    else:
                        body_lines.append(f"    {repo_name}.save({record_var});")
                else:
                    # Standard column-by-column INSERT
                    table = insert.get('table', '')
                    entity_name = PLSQLtoJavaConverter._table_to_entity(table)
                    columns = insert.get('columns', [])
                    values = insert.get('values', [])
                    repo_name = PLSQLtoJavaConverter._table_to_repository_name(table)
                    
                    body_lines.append(f"    {entity_name} entity = new {entity_name}();")
                    
                    for col, val in zip(columns, values):
                        col_camel = PLSQLtoJavaConverter._to_camel_case(col)
                        setter = 'set' + col_camel[0].upper() + col_camel[1:] if col_camel else ''
                        val_java = PLSQLtoJavaConverter._translate_plsql_expression(val)
                        body_lines.append(f"    entity.{setter}({val_java});")
                    
                    if insert.get('returning_column'):
                        returning_var = PLSQLtoJavaConverter._to_camel_case(insert.get('returning_into', 'resultId'))
                        body_lines.append(f"    Long {returning_var} = {repo_name}.save(entity).getId();")
                        if returning_var not in declared_vars:
                            declared_vars.add(returning_var)
                    else:
                        body_lines.append(f"    {repo_name}.save(entity);")
            
            # Handle UPDATEs
            for update in logic.updates:
                table = update.get('table', '')
                entity_name = PLSQLtoJavaConverter._table_to_entity(table)
                assignments = update.get('assignments', {})
                where_clause = update.get('where', '')
                repo_name = PLSQLtoJavaConverter._table_to_repository_name(table)

                # Derive the lookup expression from the WHERE clause
                # e.g. "customer_id = p_customer_id" -> findById(customerId)
                find_call = None
                if where_clause:
                    java_where = PLSQLtoJavaConverter._translate_plsql_expression(where_clause)
                    id_match = re.search(r'=\s*([pl]_\w+)\b', java_where, re.IGNORECASE)
                    if id_match:
                        id_param_camel = PLSQLtoJavaConverter._to_camel_case(id_match.group(1))
                        find_call = f"{repo_name}.findById({id_param_camel})"
                    else:
                        # Try to find a plain id reference like "= customerId"
                        plain_id = re.search(r'=\s*(\w+)\b', java_where)
                        if plain_id:
                            find_call = f"{repo_name}.findById({plain_id.group(1)})"

                if find_call is None:
                    # Fallback: derive parameter name from assignments values
                    # e.g. assignments has value p_customer_id somewhere
                    id_from_assignments = None
                    for val in assignments.values():
                        m = re.search(r'\b([pl]_\w*id\w*)\b', val, re.IGNORECASE)
                        if m:
                            id_from_assignments = PLSQLtoJavaConverter._to_camel_case(m.group(1))
                            break
                    if id_from_assignments:
                        find_call = f"{repo_name}.findById({id_from_assignments})"
                    else:
                        find_call = f"{repo_name}.findById(id)"  # last-resort placeholder

                body_lines.append(f"    Optional<{entity_name}> existingOpt = {find_call};")
                body_lines.append(f"    if (existingOpt.isPresent()) {{")
                body_lines.append(f"        var existing = existingOpt.get();")

                for col, val in assignments.items():
                    col_camel = PLSQLtoJavaConverter._to_camel_case(col)
                    setter = 'set' + col_camel[0].upper() + col_camel[1:] if col_camel else ''
                    val_java = PLSQLtoJavaConverter._translate_plsql_expression(val)
                    body_lines.append(f"        existing.{setter}({val_java});")

                body_lines.append(f"        {repo_name}.save(existing);")
                body_lines.append(f"    }}")
            
            # Handle DELETEs
            for delete in logic.deletes:
                table = delete.get('table', '')
                where = delete.get('where', '')
                entity_name = PLSQLtoJavaConverter._table_to_entity(table)
                repo_name = PLSQLtoJavaConverter._table_to_repository_name(table)
                
                if where and where.strip():
                    java_where = PLSQLtoJavaConverter._translate_plsql_expression(where)
                    # Try to extract ID from where clause
                    id_match = re.search(r'=\s*([pl]_\w+)\b', java_where, re.IGNORECASE)
                    if id_match:
                        id_param = id_match.group(1)
                        id_param_camel = PLSQLtoJavaConverter._to_camel_case(id_param)
                        body_lines.append(f"    {repo_name}.deleteById({id_param_camel});")
                    else:
                        body_lines.append(f"    {repo_name}.deleteByCondition({java_where});")
                else:
                    body_lines.append(f"    // DELETE from {table}")
        
        # 5. RETURN STATEMENT
        if logic.returns and return_type != 'void':
            # Determine what variable to return
            return_var = None

            # If there's an INSERT with RETURNING, return that ID
            for insert in logic.inserts:
                if insert.get('returning_into'):
                    return_var = PLSQLtoJavaConverter._to_camel_case(insert.get('returning_into', 'resultId'))
                    break

            # If no INSERT RETURNING, use the first RETURN statement
            if not return_var and logic.returns:
                first_return = logic.returns[0]
                return_var = PLSQLtoJavaConverter._to_camel_case(first_return)

            # FIX: When the return type is a scalar (String, Long, BigDecimal …) but the
            # body fetched an entity via SELECT, we must project the right field out of
            # the entity instead of returning the whole entity object.
            #
            # Heuristic: if `return_var` matches a SELECT into-variable (i.e. an entity
            # opt), emit entity.getField() using the into-variable name as a getter suffix.
            if return_var and return_type not in ('Object', 'void'):
                # Check whether return_var is actually an entity variable (ends with 'Opt'
                # or is a SELECT into var)
                entity_vars = {PLSQLtoJavaConverter._to_camel_case(s.get('into_variables', ''))
                               for s in logic.selects if s.get('into_variables')}
                is_entity_var = (return_var + 'Opt') in declared_vars or return_var in entity_vars

                if is_entity_var:
                    # The SELECT used return_var as into-variable; the getter is
                    # entity.get<ReturnVar>(), e.g. customer.getCustomerName()
                    getter = 'get' + return_var[0].upper() + return_var[1:]
                    body_lines.append(f"    if ({return_var} == null) return null;")
                    body_lines.append(f"    return {return_var}.{getter}();")
                else:
                    body_lines.append(f"    return {return_var};")
            elif return_var:
                body_lines.append(f"    return {return_var};")
        
        # Build final method
        final_code = ""
        if logic.has_commit or logic.inserts or logic.updates or logic.deletes or logic.logging_calls:
            if logic.has_autonomous_transaction:
                final_code += "    @Transactional(propagation = org.springframework.transaction.annotation.Propagation.REQUIRES_NEW)\n"
            else:
                final_code += "    @Transactional\n"
        
        final_code += f"public {return_type} {method_name}({params_str}) {{\n"
        final_code += "\n".join(body_lines) if body_lines else "        logger.info(\"Method executed\");"
        final_code += "\n    }\n"
        
        # ========== COMPLIANCE ENFORCEMENT (Rule 1-12) ==========
        if COMPLIANCE_ENFORCER_AVAILABLE:
            corrected_code, is_compliant, violations = enforce_java_compliance(
                final_code, 
                method_name=method_name
            )
            if not is_compliant:
                logger.warning(f"\n{'='*80}")
                logger.warning(f"COMPLIANCE VIOLATIONS in method '{method_name}':")
                for violation in violations:
                    logger.warning(f"  ⚠ {violation}")
                logger.warning(f"{'='*80}\n")
            final_code = corrected_code
        # ============================================================
        
        return final_code
    
    @staticmethod
    def _convert_plsql_var_names(java_code: str) -> str:
        """
        Convert all p_xxx, l_xxx, v_xxx variable names to camelCase.
        This ensures generated Java doesn't contain PL/SQL naming conventions.
        
        Examples:
            p_customer_id -> customerId
            l_vat_rate -> vatRate
            v_result -> result
        """
        # Replace p_, l_, v_ prefixed variables with camelCase versions
        def replace_var(m):
            full_var = m.group(0)
            # Extract the part after the prefix (p_, l_, v_)
            var_part = m.group(1)
            # Convert to camelCase
            camel = PLSQLtoJavaConverter._to_camel_case(var_part)
            return camel
        
        # Match p_xxx, l_xxx, v_xxx (must be complete words)
        # But avoid matching inside method calls like .setP... or .getL...
        result = re.sub(r'\b[plv]_([a-zA-Z_]\w*)\b', replace_var, java_code)
        
        return result
    
    @staticmethod
    def fix_malformed_method(class_code: str, method_name: str, corrected_impl: str) -> str:
        """
        Replace malformed method with corrected implementation.
        """
        # Find and replace the malformed method
        pattern = rf'public\s+\w+\s+{method_name}\s*\([^)]*\)\s*\{{[^}}]*\}}'
        
        if re.search(pattern, class_code):
            return re.sub(pattern, corrected_impl, class_code, flags=re.DOTALL)
        
        return class_code
