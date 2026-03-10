"""
SQL to JPA Conversion Engine for PL/SQL Modernization Platform
Converts SQL queries to JPA entities and repository methods
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ColumnInfo:
    """Information about a database column"""
    name: str
    data_type: str
    nullable: bool = True
    primary_key: bool = False
    foreign_key: bool = False
    unique: bool = False
    length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None


@dataclass
class TableInfo:
    """Information about a database table"""
    name: str
    schema: Optional[str] = None
    columns: List[ColumnInfo] = None
    primary_keys: List[str] = None
    foreign_keys: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.columns is None:
            self.columns = []
        if self.primary_keys is None:
            self.primary_keys = []
        if self.foreign_keys is None:
            self.foreign_keys = []


@dataclass
class RelationshipInfo:
    """Information about table relationships"""
    source_table: str
    target_table: str
    source_column: str
    target_column: str
    relationship_type: str  # one-to-one, one-to-many, many-to-one, many-to-many


class SQLToJPAConverter:
    """Converts SQL queries to JPA entities and repository methods"""
    
    def __init__(self):
        """Initialize SQL to JPA converter"""
        self.type_mappings = self._get_type_mappings()
        self.sql_analyzer = SQLAnalyzer()
    
    def convert_sql_to_entities(self, sql_queries: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Convert SQL queries to JPA entities
        
        Args:
            sql_queries (List[Dict[str, Any]]): List of SQL queries
            
        Returns:
            Dict[str, str]: Generated JPA entity classes
        """
        logger.info(f"Converting {len(sql_queries)} SQL queries to JPA entities...")
        
        # Analyze tables and columns from SQL queries
        table_info = self._analyze_tables_from_queries(sql_queries)
        
        # Generate entities
        entities = {}
        for table_name, table_data in table_info.items():
            entity_code = self._generate_entity_class(table_data)
            entity_filename = f"{table_name}Entity.java"
            entities[entity_filename] = entity_code
        
        logger.info(f"Generated {len(entities)} JPA entity classes")
        return entities
    
    def convert_sql_to_repositories(self, sql_queries: List[Dict[str, Any]], 
                                   entities: Dict[str, str]) -> Dict[str, str]:
        """
        Convert SQL queries to JPA repository methods
        
        Args:
            sql_queries (List[Dict[str, Any]]): List of SQL queries
            entities (Dict[str, str]): Generated entity classes
            
        Returns:
            Dict[str, str]: Generated JPA repository interfaces
        """
        logger.info(f"Converting {len(sql_queries)} SQL queries to JPA repositories...")
        
        # Group queries by table
        table_queries = self._group_queries_by_table(sql_queries)
        
        # Generate repositories
        repositories = {}
        for table_name, queries in table_queries.items():
            repo_code = self._generate_repository_interface(table_name, queries)
            repo_filename = f"{table_name}Repository.java"
            repositories[repo_filename] = repo_code
        
        logger.info(f"Generated {len(repositories)} JPA repository interfaces")
        return repositories
    
    def _analyze_tables_from_queries(self, sql_queries: List[Dict[str, Any]]) -> Dict[str, TableInfo]:
        """Analyze tables and columns from SQL queries"""
        table_info = {}
        
        for query in sql_queries:
            query_text = query.get('query', '')
            tables = query.get('tables', [])
            
            # Analyze each table in the query
            for table in tables:
                if table not in table_info:
                    table_info[table] = TableInfo(name=table)
                
                # Extract column information
                columns = self._extract_columns_from_query(query_text, table)
                for col_info in columns:
                    # Check if column already exists
                    existing_col = next((c for c in table_info[table].columns if c.name == col_info.name), None)
                    if existing_col:
                        # Update existing column info
                        existing_col.nullable = existing_col.nullable and col_info.nullable
                        if col_info.primary_key:
                            existing_col.primary_key = True
                            if col_info.name not in table_info[table].primary_keys:
                                table_info[table].primary_keys.append(col_info.name)
                    else:
                        # Add new column
                        table_info[table].columns.append(col_info)
                        if col_info.primary_key and col_info.name not in table_info[table].primary_keys:
                            table_info[table].primary_keys.append(col_info.name)
        
        # Analyze relationships
        relationships = self._analyze_relationships(sql_queries)
        for rel in relationships:
            # Update foreign key information
            if rel.source_column in [c.name for c in table_info[rel.source_table].columns]:
                for col in table_info[rel.source_table].columns:
                    if col.name == rel.source_column:
                        col.foreign_key = True
                        break
        
        return table_info
    
    def _extract_columns_from_query(self, query_text: str, table_name: str) -> List[ColumnInfo]:
        """Extract column information from SQL query"""
        columns = []
        
        # Extract SELECT columns
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', query_text, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_clause = select_match.group(1)
            # Parse column names from SELECT clause
            column_names = self._parse_select_columns(select_clause)
            for col_name in column_names:
                col_info = ColumnInfo(
                    name=col_name,
                    data_type='String',  # Default type, will be refined
                    nullable=True
                )
                columns.append(col_info)
        
        # Extract WHERE conditions to identify primary keys
        where_match = re.search(r'WHERE\s+(.*?)($|ORDER|GROUP|LIMIT)', query_text, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1)
            # Look for primary key patterns in WHERE clause
            pk_patterns = [
                r'(\w+)\s*=\s*[^=]',  # column = value
                r'(\w+)\s+IN\s*\(',   # column IN (...)
            ]
            for pattern in pk_patterns:
                matches = re.findall(pattern, where_clause, re.IGNORECASE)
                for match in matches:
                    for col in columns:
                        if col.name.lower() == match.lower():
                            col.primary_key = True
        
        # Set default data types based on column names
        for col in columns:
            col.data_type = self._infer_data_type(col.name, query_text)
        
        return columns
    
    def _parse_select_columns(self, select_clause: str) -> List[str]:
        """Parse column names from SELECT clause"""
        # Remove function calls and aliases
        clean_clause = re.sub(r'\w+\s*\([^)]*\)', '', select_clause)  # Remove function calls
        clean_clause = re.sub(r'\s+AS\s+\w+', '', clean_clause, flags=re.IGNORECASE)  # Remove aliases
        
        # Split by comma and clean up
        column_names = []
        for col in clean_clause.split(','):
            col = col.strip()
            if col and not col.upper() in ['*', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN']:
                # Extract just the column name
                col_name = col.split('.')[-1].strip()
                if col_name:
                    column_names.append(col_name)
        
        return column_names
    
    def _infer_data_type(self, column_name: str, query_text: str) -> str:
        """Infer Java data type from column name and context"""
        column_name_lower = column_name.lower()
        
        # ID columns are usually Long
        if column_name_lower.endswith('_id') or column_name_lower == 'id':
            return 'Long'
        
        # Name columns are usually String
        if any(name_word in column_name_lower for name_word in ['name', 'title', 'description']):
            return 'String'
        
        # Date/time columns
        if any(date_word in column_name_lower for date_word in ['date', 'time', 'created', 'updated']):
            return 'LocalDateTime'
        
        # Numeric columns
        if any(num_word in column_name_lower for num_word in ['amount', 'price', 'count', 'number', 'qty']):
            return 'BigDecimal'
        
        # Boolean columns
        if any(bool_word in column_name_lower for bool_word in ['is_', 'has_', 'enabled', 'active']):
            return 'Boolean'
        
        # Check query context for more clues
        if 'VARCHAR' in query_text.upper() or 'CHAR' in query_text.upper():
            return 'String'
        elif 'NUMBER' in query_text.upper() or 'INT' in query_text.upper():
            return 'Long'
        elif 'DATE' in query_text.upper() or 'TIME' in query_text.upper():
            return 'LocalDateTime'
        elif 'DECIMAL' in query_text.upper() or 'FLOAT' in query_text.upper():
            return 'BigDecimal'
        
        # Default to String
        return 'String'
    
    def _analyze_relationships(self, sql_queries: List[Dict[str, Any]]) -> List[RelationshipInfo]:
        """Analyze table relationships from SQL queries"""
        relationships = []
        
        for query in sql_queries:
            query_text = query.get('query', '')
            tables = query.get('tables', [])
            
            if len(tables) > 1:
                # Look for JOIN clauses
                join_matches = re.findall(r'JOIN\s+(\w+).*?ON\s+(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)', 
                                        query_text, re.IGNORECASE)
                
                for match in join_matches:
                    target_table, source_table, source_col, target_table2, target_col = match
                    
                    # Determine relationship type
                    rel_type = self._determine_relationship_type(query_text, source_col, target_col)
                    
                    rel_info = RelationshipInfo(
                        source_table=source_table,
                        target_table=target_table,
                        source_column=source_col,
                        target_column=target_col,
                        relationship_type=rel_type
                    )
                    relationships.append(rel_info)
        
        return relationships
    
    def _determine_relationship_type(self, query_text: str, source_col: str, target_col: str) -> str:
        """Determine relationship type from query context"""
        # Look for clues in the query
        if 'LEFT JOIN' in query_text.upper():
            return 'one-to-many'
        elif 'INNER JOIN' in query_text.upper():
            return 'many-to-one'
        elif 'UNIQUE' in query_text.upper() or 'PRIMARY KEY' in query_text.upper():
            return 'one-to-one'
        else:
            return 'many-to-one'
    
    def _generate_entity_class(self, table_info: TableInfo) -> str:
        """Generate JPA entity class"""
        entity_name = self._to_camel_case(table_info.name, capitalize=True)
        
        # Generate imports
        imports = self._generate_entity_imports(table_info)
        
        # Generate class annotations
        annotations = self._generate_entity_annotations(table_info)
        
        # Generate fields
        fields = self._generate_entity_fields(table_info)
        
        # Generate constructors
        constructors = self._generate_entity_constructors(entity_name, table_info)
        
        # Generate getters and setters
        getters_setters = self._generate_getters_setters(table_info)
        
        # Generate toString method
        to_string = self._generate_to_string_method(entity_name, table_info)
        
        # Combine all parts
        entity_code = f"""package com.company.project.entity;

{imports}

{annotations}
public class {entity_name} {{
    
{fields}
    
{constructors}
    
{getters_setters}
    
{to_string}
}}
"""
        
        return entity_code
    
    def _generate_entity_imports(self, table_info: TableInfo) -> str:
        """Generate imports for entity class"""
        imports = [
            'import javax.persistence.*;',
            'import java.time.LocalDateTime;',
            'import java.math.BigDecimal;',
            'import java.util.Objects;'
        ]
        
        # Check if any relationships exist
        has_relationships = any(col.foreign_key for col in table_info.columns)
        if has_relationships:
            imports.append('import java.util.List;')
            imports.append('import javax.persistence.OneToMany;')
            imports.append('import javax.persistence.ManyToOne;')
            imports.append('import javax.persistence.JoinColumn;')
        
        return '\n'.join(imports)
    
    def _generate_entity_annotations(self, table_info: TableInfo) -> str:
        """Generate entity annotations"""
        table_annotation = f"@Entity\n@Table(name = \"{table_info.name}\")"
        
        # Add additional annotations based on table properties
        annotations = [table_annotation]
        
        return '\n'.join(annotations)
    
    def _generate_entity_fields(self, table_info: TableInfo) -> str:
        """Generate entity fields"""
        fields = []
        
        for col in table_info.columns:
            # Generate column annotation
            col_annotation = f"@Column(name = \"{col.name}\""
            if col.primary_key:
                col_annotation += ", nullable = false"
            if col.unique:
                col_annotation += ", unique = true"
            col_annotation += ")"
            
            # Generate field declaration
            field_type = self.type_mappings.get(col.data_type, col.data_type)
            field_name = self._to_camel_case(col.name)
            
            field_declaration = f"    private {field_type} {field_name};"
            
            # Add getter/setter comments
            comment = f"    // {col.name} column"
            
            fields.extend([f"    {col_annotation}", f"    {field_declaration}", f"    {comment}", ""])
        
        return '\n'.join(fields)
    
    def _generate_entity_constructors(self, entity_name: str, table_info: TableInfo) -> str:
        """Generate entity constructors"""
        # Default constructor
        default_constructor = f"""    public {entity_name}() {{
    }}"""
        
        # Constructor with all fields
        if table_info.columns:
            param_list = []
            assignment_list = []
            
            for col in table_info.columns:
                field_type = self.type_mappings.get(col.data_type, col.data_type)
                field_name = self._to_camel_case(col.name)
                param_list.append(f"{field_type} {field_name}")
                assignment_list.append(f"        this.{field_name} = {field_name};")
            
            all_fields_constructor = f"""    
    public {entity_name}({', '.join(param_list)}) {{
{chr(10).join(assignment_list)}
    }}"""
        else:
            all_fields_constructor = ""
        
        return default_constructor + all_fields_constructor
    
    def _generate_getters_setters(self, table_info: TableInfo) -> str:
        """Generate getter and setter methods"""
        methods = []
        
        for col in table_info.columns:
            field_type = self.type_mappings.get(col.data_type, col.data_type)
            field_name = self._to_camel_case(col.name)
            method_name = field_name[0].upper() + field_name[1:]
            
            getter = f"""    public {field_type} get{method_name}() {{
        return {field_name};
    }}
    
    public void set{method_name}({field_type} {field_name}) {{
        this.{field_name} = {field_name};
    }}
"""
            methods.append(getter)
        
        return '\n'.join(methods)
    
    def _generate_to_string_method(self, entity_name: str, table_info: TableInfo) -> str:
        """Generate toString method"""
        if not table_info.columns:
            return f"""    @Override
    public String toString() {{
        return "{entity_name}{{}}";
    }}"""
        
        field_strings = []
        for col in table_info.columns:
            field_name = self._to_camel_case(col.name)
            field_strings.append(f"{col.name}=" + "' + " + f"{field_name} + '")
        
        return f"""    @Override
    public String toString() {{
        return "{entity_name}{{" +
                "{', '.join(field_strings)}" +
                "}}";
    }}"""
    
    def _generate_repository_interface(self, table_name: str, queries: List[Dict[str, Any]]) -> str:
        """Generate JPA repository interface"""
        entity_name = self._to_camel_case(table_name, capitalize=True)
        repo_name = f"{entity_name}Repository"
        
        # Generate imports
        imports = self._generate_repository_imports()
        
        # Generate interface declaration
        interface_decl = f"""public interface {repo_name} extends JpaRepository<{entity_name}, Long> {{"""
        
        # Generate custom query methods
        custom_methods = self._generate_custom_query_methods(queries, entity_name)
        
        # Close interface
        close_interface = "}"
        
        # Combine all parts
        repo_code = f"""package com.company.project.repository;

{imports}

{interface_decl}

{custom_methods}
{close_interface}
"""
        
        return repo_code
    
    def _generate_repository_imports(self) -> str:
        """Generate imports for repository interface"""
        return """import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import com.company.project.entity.*;"""
    
    def _generate_custom_query_methods(self, queries: List[Dict[str, Any]], entity_name: str) -> str:
        """Generate custom query methods for repository"""
        methods = []
        
        for i, query in enumerate(queries):
            query_text = query.get('query', '')
            query_type = query.get('query_type', 'SELECT').upper()
            
            if query_type == 'SELECT':
                # Generate method name based on query
                method_name = self._generate_method_name(query_text, query_type)
                
                # Convert SQL to JPQL
                jpql_query = self._convert_sql_to_jpql(query_text, entity_name)
                
                method = f"""    @Query("{jpql_query}")
    List<{entity_name}> {method_name}();"""
                
                methods.append(method)
        
        return '\n\n'.join(methods) if methods else "    // Custom query methods can be added here"
    
    def _generate_method_name(self, query_text: str, query_type: str) -> str:
        """Generate method name based on SQL query"""
        # Extract key words from query
        if 'WHERE' in query_text.upper():
            where_part = query_text.split('WHERE')[1].split('ORDER')[0].split('GROUP')[0]
            # Extract column names from WHERE clause
            columns = re.findall(r'(\w+)\s*[=<>!]', where_part)
            if columns:
                return f"findBy{self._to_camel_case(columns[0], capitalize=True)}"
        
        return f"find{query_type}Query"
    
    def _convert_sql_to_jpql(self, sql_query: str, entity_name: str) -> str:
        """Convert SQL query to JPQL"""
        # Simple conversion - in a real implementation, this would be more sophisticated
        jpql = sql_query.replace('SELECT', f'SELECT e FROM {entity_name} e')
        jpql = re.sub(r'FROM\s+\w+', f'FROM {entity_name} e', jpql, flags=re.IGNORECASE)
        jpql = re.sub(r'JOIN\s+(\w+)', r'JOIN e.\1', jpql, flags=re.IGNORECASE)
        
        return jpql
    
    def _group_queries_by_table(self, sql_queries: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group SQL queries by table"""
        table_queries = {}
        
        for query in sql_queries:
            tables = query.get('tables', [])
            for table in tables:
                if table not in table_queries:
                    table_queries[table] = []
                table_queries[table].append(query)
        
        return table_queries
    
    def _to_camel_case(self, text: str, capitalize: bool = False) -> str:
        """Convert text to camel case"""
        words = re.findall(r'[a-zA-Z0-9]+', text)
        if not words:
            return text
        
        result = ''.join(word.capitalize() if i > 0 else word.lower() 
                        for i, word in enumerate(words))
        
        if capitalize:
            result = result[0].upper() + result[1:]
        
        return result
    
    def _get_type_mappings(self) -> Dict[str, str]:
        """Get SQL to Java type mappings"""
        return {
            'String': 'String',
            'Long': 'Long',
            'Integer': 'Integer',
            'BigDecimal': 'BigDecimal',
            'Double': 'Double',
            'Float': 'Float',
            'Boolean': 'Boolean',
            'LocalDateTime': 'LocalDateTime',
            'Date': 'LocalDateTime',
            'Timestamp': 'LocalDateTime'
        }


class SQLAnalyzer:
    """Analyzes SQL queries for conversion patterns"""
    
    def __init__(self):
        """Initialize SQL analyzer"""
        self.patterns = {
            'select': r'(?i)SELECT\s+.*?\s+FROM',
            'insert': r'(?i)INSERT\s+INTO\s+.*?\s+VALUES',
            'update': r'(?i)UPDATE\s+.*?\s+SET',
            'delete': r'(?i)DELETE\s+FROM\s+.*?',
            'join': r'(?i)(LEFT|RIGHT|INNER|FULL)\s+JOIN\s+(\w+)',
            'where': r'(?i)WHERE\s+.*?(?:ORDER|GROUP|LIMIT|$)',
            'order': r'(?i)ORDER\s+BY\s+.*?(?:LIMIT|$)',
            'group': r'(?i)GROUP\s+BY\s+.*?(?:HAVING|ORDER|LIMIT|$)'
        }
    
    def analyze_query(self, query_text: str) -> Dict[str, Any]:
        """Analyze SQL query structure"""
        analysis = {
            'query_type': self._identify_query_type(query_text),
            'tables': self._extract_tables(query_text),
            'columns': self._extract_columns(query_text),
            'conditions': self._extract_conditions(query_text),
            'joins': self._extract_joins(query_text),
            'order_by': self._extract_order_by(query_text),
            'group_by': self._extract_group_by(query_text)
        }
        
        return analysis
    
    def _identify_query_type(self, query_text: str) -> str:
        """Identify the type of SQL query"""
        query_upper = query_text.strip().upper()
        
        if query_upper.startswith('SELECT'):
            return 'SELECT'
        elif query_upper.startswith('INSERT'):
            return 'INSERT'
        elif query_upper.startswith('UPDATE'):
            return 'UPDATE'
        elif query_upper.startswith('DELETE'):
            return 'DELETE'
        elif query_upper.startswith('MERGE'):
            return 'MERGE'
        else:
            return 'UNKNOWN'
    
    def _extract_tables(self, query_text: str) -> List[str]:
        """Extract table names from query"""
        tables = []
        
        # Extract FROM clause
        from_match = re.search(r'FROM\s+([^WHERE|ORDER|GROUP|LIMIT|;]+)', query_text, re.IGNORECASE)
        if from_match:
            from_clause = from_match.group(1).strip()
            # Split by JOIN or comma
            table_parts = re.split(r'\s+(?:JOIN|,)\s+', from_clause, flags=re.IGNORECASE)
            for part in table_parts:
                # Extract table name (remove aliases)
                table_name = part.split()[0].strip()
                if table_name and table_name not in tables:
                    tables.append(table_name)
        
        return tables
    
    def _extract_columns(self, query_text: str) -> List[str]:
        """Extract column names from query"""
        columns = []
        
        # Extract SELECT columns
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', query_text, re.IGNORECASE)
        if select_match:
            select_clause = select_match.group(1)
            # Remove function calls and aliases
            clean_clause = re.sub(r'\w+\s*\([^)]*\)', '', select_clause)
            clean_clause = re.sub(r'\s+AS\s+\w+', '', clean_clause, flags=re.IGNORECASE)
            
            for col in clean_clause.split(','):
                col = col.strip()
                if col and col != '*':
                    # Extract just the column name
                    col_name = col.split('.')[-1].strip()
                    if col_name:
                        columns.append(col_name)
        
        return columns
    
    def _extract_conditions(self, query_text: str) -> List[str]:
        """Extract WHERE conditions"""
        conditions = []
        
        where_match = re.search(r'WHERE\s+(.*?)(?:ORDER|GROUP|LIMIT|$)', query_text, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1).strip()
            # Split by AND/OR
            condition_parts = re.split(r'\s+(?:AND|OR)\s+', where_clause, flags=re.IGNORECASE)
            conditions.extend([part.strip() for part in condition_parts if part.strip()])
        
        return conditions
    
    def _extract_joins(self, query_text: str) -> List[Dict[str, str]]:
        """Extract JOIN information"""
        joins = []
        
        join_matches = re.findall(r'(LEFT|RIGHT|INNER|FULL)\s+JOIN\s+(\w+)', query_text, re.IGNORECASE)
        for join_type, table_name in join_matches:
            joins.append({
                'type': join_type.upper(),
                'table': table_name
            })
        
        return joins
    
    def _extract_order_by(self, query_text: str) -> List[str]:
        """Extract ORDER BY columns"""
        order_columns = []
        
        order_match = re.search(r'ORDER\s+BY\s+(.*?)(?:LIMIT|$)', query_text, re.IGNORECASE)
        if order_match:
            order_clause = order_match.group(1).strip()
            order_columns = [col.strip() for col in order_clause.split(',')]
        
        return order_columns
    
    def _extract_group_by(self, query_text: str) -> List[str]:
        """Extract GROUP BY columns"""
        group_columns = []
        
        group_match = re.search(r'GROUP\s+BY\s+(.*?)(?:HAVING|ORDER|LIMIT|$)', query_text, re.IGNORECASE)
        if group_match:
            group_clause = group_match.group(1).strip()
            group_columns = [col.strip() for col in group_clause.split(',')]
        
        return group_columns


def create_sql_to_jpa_converter() -> SQLToJPAConverter:
    """Create and return a configured SQL to JPA converter"""
    return SQLToJPAConverter()