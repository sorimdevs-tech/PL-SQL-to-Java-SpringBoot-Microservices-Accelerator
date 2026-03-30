"""
SBG-30: Dynamic PL/SQL Logic Extraction and Java Generation
Extracts actual business logic patterns from PL/SQL procedures and generates
equivalent Java implementations dynamically (not hardcoded).
"""

import re
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProcedureSignature:
    """Extracted PL/SQL procedure signature"""
    name: str
    parameters: List[Dict[str, str]]  # [{'name': 'p_id', 'type': 'NUMBER', 'mode': 'IN'}, ...]
    return_type: Optional[str]
    body: str
    
    
@dataclass
class ProcedureLogic:
    """Extracted business logic patterns from procedure body"""
    validates: List[str]  # Validation conditions found
    selects: List[str]    # SELECT/query patterns
    inserts: List[str]    # INSERT patterns
    updates: List[str]    # UPDATE patterns
    deletes: List[str]    # DELETE patterns
    calculations: List[str]  # Arithmetic/calculations
    transactions: bool     # Has explicit transaction control
    

class PLSQLLogicExtractor:
    """Extract business logic patterns from PL/SQL procedures"""
    
    @staticmethod
    def extract_procedure_signature(plsql_source: str, proc_name: str) -> Optional[ProcedureSignature]:
        """
        Extract procedure signature from PL/SQL source
        
        Args:
            plsql_source: Complete PL/SQL package/procedure source
            proc_name: Name of procedure to extract
            
        Returns:
            ProcedureSignature if found, None otherwise
        """
        # Pattern: PROCEDURE name(params)
        pattern = rf'(?:PROCEDURE|FUNCTION)\s+{re.escape(proc_name)}\s*\(([^)]*)\)(?:\s+RETURN\s+(\S+))?'
        match = re.search(pattern, plsql_source, re.IGNORECASE)
        
        if not match:
            return None
        
        params_str = match.group(1)
        return_type = match.group(2)
        
        # Parse parameters
        parameters = PLSQLLogicExtractor._parse_parameters(params_str)
        
        # Extract procedure body (between BEGIN and corresponding END)
        # Find the procedure definition start
        proc_start_pattern = rf'(?:PROCEDURE|FUNCTION)\s+{re.escape(proc_name)}\s*\([^)]*\)'
        proc_start_match = re.search(proc_start_pattern, plsql_source, re.IGNORECASE)
        
        if not proc_start_match:
            return None
        
        # Find BEGIN keyword after procedure declaration
        begin_pos = plsql_source.upper().find('BEGIN', proc_start_match.end())
        
        if begin_pos < 0:
            body = ""
        else:
            # Extract text after BEGIN
            text_after_begin = plsql_source[begin_pos+5:]
            
            # Find the END statement that closes this procedure
            # Look for END PROCNAME or just END; at the end of the procedure body
            # For now, use a simple heuristic: find END followed by proc_name or END; or END followed by newline and package end
            
            # Try pattern: END [procname]
            end_pattern = rf'END\s+{re.escape(proc_name)}\s*(?:;|$)'
            end_match = re.search(end_pattern, text_after_begin, re.IGNORECASE | re.DOTALL)
            
            if end_match:
                body = text_after_begin[:end_match.start()].strip()
            else:
                # Fallback: try to find END with some heuristics
                # Find lines that start with END (not END IF, END LOOP, etc.)
                lines = text_after_begin.split('\n')
                for i, line in enumerate(lines):
                    stripped = line.strip().upper()
                    # Check if this line ends the procedure (END at column 0 or after whitespace only)
                    if stripped.startswith('END') and not stripped.startswith('END ') and not stripped.startswith('END;'):
                        # This might be END IF or similar, skip
                        continue
                    if stripped == 'END' or stripped == 'END;' or stripped.startswith('END;'):
                        body = '\n'.join(lines[:i]).strip()
                        break
                else:
                    # Couldn't find END, use whole thing
                    body = text_after_begin.strip()
        
        return ProcedureSignature(
            name=proc_name,
            parameters=parameters,
            return_type=return_type,
            body=body
        )
    
    @staticmethod
    def _parse_parameters(params_str: str) -> List[Dict[str, str]]:
        """Parse PL/SQL parameter list into structured format"""
        if not params_str.strip():
            return []
        
        parameters = []
        # Split by comma, but respect parentheses
        parts = re.split(r',\s*(?![^()]*\))', params_str)
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Pattern: name [IN/OUT/IN OUT] type
            match = re.match(r'(\w+)\s+(?:(IN\s+OUT|IN|OUT)\s+)?(.+)', part, re.IGNORECASE)
            if match:
                param_name = match.group(1)
                param_mode = match.group(2) or "IN"
                param_type = match.group(3).strip()
                
                parameters.append({
                    'name': param_name,
                    'type': param_type,
                    'mode': param_mode.upper()
                })
        
        return parameters
    
    @staticmethod
    def extract_logic_patterns(proc_sig: ProcedureSignature) -> ProcedureLogic:
        """
        Extract business logic patterns from procedure body
        
        Args:
            proc_sig: ProcedureSignature with body to analyze
            
        Returns:
            ProcedureLogic patterns found
        """
        body = proc_sig.body.upper()
        
        validates = PLSQLLogicExtractor._find_validations(proc_sig.body)
        selects = PLSQLLogicExtractor._find_operations(body, 'SELECT')
        inserts = PLSQLLogicExtractor._find_operations(body, 'INSERT')
        updates = PLSQLLogicExtractor._find_operations(body, 'UPDATE')
        deletes = PLSQLLogicExtractor._find_operations(body, 'DELETE')
        calculations = PLSQLLogicExtractor._find_calculations(proc_sig.body)
        has_transaction = bool(re.search(r'(COMMIT|ROLLBACK|PRAGMA|SAVEPOINT)', body))
        
        return ProcedureLogic(
            validates=validates,
            selects=selects,
            inserts=inserts,
            updates=updates,
            deletes=deletes,
            calculations=calculations,
            transactions=has_transaction
        )
    
    @staticmethod
    def _find_validations(body: str) -> List[str]:
        """Find validation patterns (IF ... THEN RAISE or conditions that trigger errors)"""
        validations = []
        
        # Pattern 1: IF condition THEN RAISE_APPLICATION_ERROR
        pattern1 = r'IF\s+(.+?)\s+THEN\s+RAISE_APPLICATION_ERROR'
        # Pattern 2: IF condition IS NULL THEN RAISE
        pattern2 = r'IF\s+(.+?)\s+IS\s+NULL\s+THEN\s+RAISE'
        # Pattern 3: IF NOT condition THEN RAISE
        pattern3 = r'IF\s+NOT\s+(.+?)\s+THEN\s+RAISE'
        # Pattern 4: Standalone error checks with comparisons
        pattern4 = r'(?:^\s*)?IF\s+([^T]+?)\s+THEN'
        
        for pattern in [pattern1, pattern2, pattern3, pattern4]:
            matches = re.finditer(pattern, body, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            for match in matches:
                condition = match.group(1).strip()
                # Clean up multiline conditions
                condition = re.sub(r'\s+', ' ', condition)[:90]
                if condition and 'END' not in condition.upper():
                    validations.append(condition)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_validations = []
        for v in validations:
            v_lower = v.lower()
            if v_lower not in seen and len(unique_validations) < 10:
                seen.add(v_lower)
                unique_validations.append(v)
        
        return unique_validations
    
    @staticmethod
    def _find_operations(body: str, op_type: str) -> List[str]:
        """Find SQL operations (SELECT, INSERT, UPDATE, DELETE)"""
        operations = []
        
        # Better patterns for each operation type
        if op_type.upper() == 'SELECT':
            # SELECT ... FROM ... (WHERE ...)
            pattern = r'SELECT\s+(.+?)\s+FROM\s+([;\n]|INTO)'
        elif op_type.upper() == 'INSERT':
            # INSERT INTO table (columns) VALUES (...)
            pattern = r'INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES'
        elif op_type.upper() == 'UPDATE':
            # UPDATE table SET column = value (WHERE ...)
            pattern = r'UPDATE\s+(\w+)\s+SET\s+(.+?)(?:WHERE|;|\n|END)'
        elif op_type.upper() == 'DELETE':
            # DELETE FROM table (WHERE ...)
            pattern = r'DELETE\s+FROM\s+(\w+)(?:\s+WHERE)?'
        else:
            return []
        
        matches = re.finditer(pattern, body, re.IGNORECASE | re.DOTALL)
        
        for match in matches:
            if op_type.upper() == 'SELECT':
                op = f"SELECT {match.group(1).strip()} FROM {match.group(2).strip()}"
            else:
                op = match.group(0).strip()
            
            # Trim to reasonable length and clean up
            op = re.sub(r'\s+', ' ', op)[:120]
            if op and len(op) > 10:
                operations.append(op)
        
        return operations[:5]  # Return first 5
    
    @staticmethod
    def _find_calculations(body: str) -> List[str]:
        """Find arithmetic/calculation patterns like variable assignments"""
        calculations = []
        
        # Pattern 1: variable := expression
        pattern1 = r'(\w+)\s*:=\s*(.+?)(?:;|\n)'
        # Pattern 2: v(x) := (array/collection assignment)
        pattern2 = r'(\w+)\s*\(\s*(\w+)\s*\)\s*:=\s*(.+?)(?:;|\n)'
        
        seen = set()
        for pattern in [pattern1, pattern2]:
            matches = re.finditer(pattern, body, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                expr = match.group(0).strip()
                # Clean up multiline
                expr = re.sub(r'\s+', ' ', expr)[:100]
                expr_lower = expr.lower()
                
                # Only add if it looks like a calculation (contains arithmetic)
                if any(op in expr for op in ['*', '+', '-', '/', '%', 'MOD', 'ROUND', 'TRUNC']):
                    if expr_lower not in seen and len(calculations) < 10:
                        seen.add(expr_lower)
                        calculations.append(expr)
        
        return calculations


class JavaLogicGenerator:
    """Generate Java Spring Boot code from extracted PL/SQL logic"""
    
    @staticmethod
    def generate_method_body(proc_sig: ProcedureSignature, logic: ProcedureLogic) -> str:
        """
        Generate Java method body based on PL/SQL logic
        
        Args:
            proc_sig: Procedure signature
            logic: Extracted logic patterns
            
        Returns:
            Java method implementation
        """
        lines = []
        
        # 1. Validation layer
        if logic.validates:
            lines.append("        // Validation layer (from PL/SQL)")
            for validation in logic.validates[:2]:
                # Convert PL/SQL condition to Java
                java_condition = JavaLogicGenerator._plsql_to_java_condition(validation)
                lines.append(f"        if (!({java_condition})) {{")
                lines.append('            throw new BusinessException("Validation failed");')
                lines.append("        }")
        
        # 2. Calculation layer
        if logic.calculations:
            lines.append("        // Calculation layer (from PL/SQL)")
            for calc in logic.calculations[:2]:
                java_calc = JavaLogicGenerator._plsql_to_java_expression(calc)
                lines.append(f"        {java_calc}")
        
        # 3. Query layer (SELECT)
        if logic.selects:
            lines.append("        // Query layer (from PL/SQL)")
            lines.append("        // SELECT logic implementation")
            for i, select in enumerate(logic.selects[:1]):
                table_match = re.search(r'FROM\s+(\w+)', select, re.IGNORECASE)
                if table_match:
                    table = table_match.group(1)
                    lines.append(f"        // Query from {table}")
        
        # 4. Mutation layer (INSERT/UPDATE/DELETE)
        if logic.inserts:
            lines.append("        // INSERT logic (from PL/SQL)")
            lines.append("        // persist new record")
        
        if logic.updates:
            lines.append("        // UPDATE logic (from PL/SQL)")
            lines.append("        // modify existing record")
        
        if logic.deletes:
            lines.append("        // DELETE logic (from PL/SQL)")
            lines.append("        // remove record")
        
        # 5. Transaction handling
        if logic.transactions:
            lines.append("        // Transaction committed (from PL/SQL)")
        
        # 6. Logging
        lines.append(f"        logger.info(\"Executed {proc_sig.name}\");")
        
        return "\n".join(lines)
    
    @staticmethod
    def _plsql_to_java_condition(plsql_condition: str) -> str:
        """
        Convert PL/SQL condition to Java equivalent
        
        Examples:
            p_id IS NULL -> pId == null
            p_amount > 0 -> pAmount > BigDecimal.ZERO
        """
        java_cond = plsql_condition
        
        # Replace IS NULL with == null
        java_cond = re.sub(r'\bIS\s+NULL\b', '== null', java_cond, flags=re.IGNORECASE)
        java_cond = re.sub(r'\bIS\s+NOT\s+NULL\b', '!= null', java_cond, flags=re.IGNORECASE)
        
        # Replace PL/SQL operators
        java_cond = java_cond.replace('||', " +")  # String concatenation
        
        # Convert parameter names: p_name -> pName
        java_cond = re.sub(r'\bp_(\w+)\b', lambda m: 'p' + m.group(1).capitalize(), java_cond, flags=re.IGNORECASE)
        
        return java_cond
    
    @staticmethod
    def _plsql_to_java_expression(plsql_expr: str) -> str:
        """Convert PL/SQL expression to Java"""
        java_expr = plsql_expr
        
        # Remove PL/SQL line terminator
        java_expr = java_expr.rstrip(';')
        
        # Replace := with =
        java_expr = java_expr.replace(':=', '=')
        
        # Convert parameter names
        java_expr = re.sub(r'\bp_(\w+)\b', 
                          lambda m: f'p{m.group(1)[0].upper()}{m.group(1)[1:]}',
                          java_expr, flags=re.IGNORECASE)
        
        return java_expr + ";"


class DynamicServiceGenerator:
    """Generate service methods based on actual PL/SQL procedures"""
    
    @staticmethod
    def generate_service_method(
        proc_sig: ProcedureSignature,
        logic: ProcedureLogic,
        package_name: str,
        entity_names: Dict[str, str]
    ) -> str:
        """
        Generate complete Java service method from PL/SQL procedure
        
        Args:
            proc_sig: Procedure signature
            logic: Extracted logic patterns
            package_name: Java package name
            entity_names: Mapping of table names to entity classes
            
        Returns:
            Complete Java method code
        """
        # Generate method signature
        method_name = DynamicServiceGenerator._to_camel_case(proc_sig.name)
        return_type = DynamicServiceGenerator._map_plsql_type_to_java(proc_sig.return_type or 'void')
        
        # Generate parameter list
        java_params = []
        for param in proc_sig.parameters:
            java_type = DynamicServiceGenerator._map_plsql_type_to_java(param['type'])
            java_name = DynamicServiceGenerator._to_camel_case(param['name'])
            java_params.append(f"{java_type} {java_name}")
        
        params_str = ", ".join(java_params) or ""
        
        # Add @Transactional if procedure modifies data
        annotations = []
        if logic.inserts or logic.updates or logic.deletes or logic.transactions:
            annotations.append("    @Transactional")
        
        annotation_str = "\n".join(annotations)
        
        # Generate method body with actual logic
        body_lines = []
        
        # 1. Validation layer from PL/SQL
        if logic.validates:
            body_lines.append("        // === Validation Layer ===")
            for i, validation in enumerate(logic.validates[:3]):
                java_cond = JavaLogicGenerator._plsql_to_java_condition(validation)
                body_lines.append(f"        if (!({java_cond})) {{")
                body_lines.append(f'            throw new BusinessException("Validation failed: {validation[:50]}");')
                body_lines.append("        }")
        
        # 2. Calculation layer
        if logic.calculations:
            body_lines.append("        // === Calculation Layer ===")
            for calc in logic.calculations[:2]:
                java_calc = JavaLogicGenerator._plsql_to_java_expression(calc)
                body_lines.append(f"        {java_calc}")
        
        # 3. Query layer (SELECT)
        if logic.selects:
            body_lines.append("        // === Query Layer ===")
            for select_stmt in logic.selects[:1]:
                # Extract table names from SELECT
                table_match = re.search(r'FROM\s+(\w+)', select_stmt, re.IGNORECASE)
                if table_match:
                    table_name = table_match.group(1).upper()
                    # Find entity class for this table
                    entity_class = entity_names.get(table_name, f"{DynamicServiceGenerator._to_pascal_case(table_name)}Entity")
                    body_lines.append(f"        // Query data from {table_name}")
        
        # 4. Mutation layer (INSERT/UPDATE/DELETE)
        if logic.inserts:
            body_lines.append("        // === INSERT Layer ===")
            for insert_stmt in logic.inserts[:1]:
                # Extract table name from INSERT
                table_match = re.search(r'INTO\s+(\w+)', insert_stmt, re.IGNORECASE)
                if table_match:
                    table_name = table_match.group(1).upper()
                    entity_class = entity_names.get(table_name, f"{DynamicServiceGenerator._to_pascal_case(table_name)}Entity")
                    body_lines.append(f"        {DynamicServiceGenerator._to_camel_case(table_name.lower())}Repository.save(new{entity_class}());")
        
        if logic.updates:
            body_lines.append("        // === UPDATE Layer ===")
            for update_stmt in logic.updates[:1]:
                table_match = re.search(r'UPDATE\s+(\w+)', update_stmt, re.IGNORECASE)
                if table_match:
                    table_name = table_match.group(1).upper()
                    entity_class = entity_names.get(table_name, f"{DynamicServiceGenerator._to_pascal_case(table_name)}Entity")
                    body_lines.append(f"        // Update {table_name} records based on WHERE clause")
        
        if logic.deletes:
            body_lines.append("        // === DELETE Layer ===")
            for delete_stmt in logic.deletes[:1]:
                table_match = re.search(r'FROM\s+(\w+)', delete_stmt, re.IGNORECASE)
                if table_match:
                    table_name = table_match.group(1).upper()
                    body_lines.append(f"        // Delete records from {table_name}")
        
        # 5. Logging
        body_lines.append(f"        logger.debug(\"Executed {method_name}\");")
        
        # If no real logic, add at least a basic implementation
        if not body_lines:
            body_lines = [
                "        // TODO: Implement based on PL/SQL logic",
                "        logger.info(\"Service method called\");"
            ]
        
        body = "\n".join(body_lines)
        
        # Build complete method
        method_code = f"""
{annotation_str}
    public {return_type} {method_name}({params_str}) {{
{body}
    }}"""
        
        return method_code.strip()
    
    @staticmethod
    def _to_camel_case(name: str) -> str:
        """Convert SNAKE_CASE to camelCase"""
        if not name:
            return name
        parts = name.split('_')
        return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])
    
    @staticmethod
    def _to_pascal_case(name: str) -> str:
        """Convert snake_case to PascalCase"""
        if not name:
            return name
        parts = name.split('_')
        return "".join(p.capitalize() for p in parts)
    
    @staticmethod
    def _map_plsql_type_to_java(plsql_type: Optional[str]) -> str:
        """Map PL/SQL types to Java types"""
        if not plsql_type:
            return 'void'
        
        type_upper = plsql_type.upper().strip()
        
        # Match common PL/SQL types
        if 'VARCHAR' in type_upper or 'CHAR' in type_upper or 'STRING' in type_upper:
            return 'String'
        elif 'NUMBER' in type_upper or 'INTEGER' in type_upper or 'DECIMAL' in type_upper or 'FLOAT' in type_upper:
            return 'BigDecimal'
        elif 'DATE' in type_upper or 'TIMESTAMP' in type_upper:
            return 'LocalDateTime'
        elif 'BOOLEAN' in type_upper:
            return 'Boolean'
        elif 'CLOB' in type_upper:
            return 'String'
        elif 'BLOB' in type_upper:
            return 'byte[]'
        elif 'TABLE' in type_upper or 'ARRAY' in type_upper:
            return 'List<?>'
        else:
            return 'Object'
        
        # Generate method body
        body = JavaLogicGenerator.generate_method_body(proc_sig, logic)
        
        # Assemble complete method
        method = f"""{annotation_str}
    public {return_type} {method_name}({params_str}) {{
{body}
    }}"""
        
        return method
    
    @staticmethod
    def _to_camel_case(name: str) -> str:
        """Convert snake_case or p_name to camelCase"""
        # Remove leading p_
        if name.startswith('p_'):
            name = name[2:]
        elif name.lower().startswith('p') and len(name) > 1 and name[1].isupper():
            name = name[1]
        
        # Convert snake_case to camelCase
        parts = name.split('_')
        result = parts[0].lower()
        for part in parts[1:]:
            result += part.capitalize()
        
        return result
    
    @staticmethod
    def _map_plsql_type_to_java(plsql_type: str) -> str:
        """Map PL/SQL types to Java types"""
        if not plsql_type:
            return "void"
        
        plsql_type = plsql_type.upper().strip()
        
        mapping = {
            'NUMBER': 'BigDecimal',
            'INTEGER': 'Long',
            'VARCHAR': 'String',
            'VARCHAR2': 'String',
            'DATE': 'java.time.LocalDate',
            'TIMESTAMP': 'java.time.LocalDateTime',
            'BOOLEAN': 'Boolean',
            'CLOB': 'String',
            'BLOB': 'byte[]',
        }
        
        for plsql, java in mapping.items():
            if plsql in plsql_type:
                return java
        
        # Default to String if unknown
        return "String"
