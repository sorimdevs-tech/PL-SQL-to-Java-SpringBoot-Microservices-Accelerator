"""
SQL Query Extractor for PL/SQL Modernization Platform
Extracts and analyzes SQL queries embedded in PL/SQL code
"""

import re
import sqlparse
from sqlparse import sql, tokens as T
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SQLQuery:
    """Represents an extracted SQL query with metadata"""
    query: str
    query_type: str  # SELECT, INSERT, UPDATE, DELETE, MERGE
    tables: List[str]
    columns: List[str]
    conditions: List[str]
    parameters: List[str]
    line_number: int
    original_context: str


@dataclass
class TableReference:
    """Represents a table reference with schema information"""
    table_name: str
    schema_name: Optional[str] = None
    alias: Optional[str] = None
    type: str = "table"  # table, view, subquery


@dataclass
class ColumnReference:
    """Represents a column reference with table information"""
    column_name: str
    table_name: Optional[str] = None
    table_alias: Optional[str] = None
    schema_name: Optional[str] = None


class SQLExtractor:
    """Extracts SQL queries from PL/SQL code"""
    
    def __init__(self):
        """Initialize SQL extractor"""
        self.sql_patterns = {
            'select': r'(?i)\bSELECT\s+.*?\s+FROM\s+.*?(?:\s+WHERE\s+.*?)?(?:\s+GROUP\s+BY\s+.*?)?(?:\s+ORDER\s+BY\s+.*?)?(?:;|\n|$)',
            'insert': r'(?i)\bINSERT\s+INTO\s+.*?\s+VALUES\s*\(.*?\)(?:;|\n|$)',
            'update': r'(?i)\bUPDATE\s+.*?\s+SET\s+.*?(?:\s+WHERE\s+.*?)?(?:;|\n|$)',
            'delete': r'(?i)\bDELETE\s+FROM\s+.*?(?:\s+WHERE\s+.*?)?(?:;|\n|$)',
            'merge': r'(?i)\bMERGE\s+INTO\s+.*?\s+USING\s+.*?\s+ON\s+.*?(?:\s+WHEN\s+MATCHED\s+THEN\s+.*?)(?:\s+WHEN\s+NOT\s+MATCHED\s+THEN\s+.*?)?(?:;|\n|$)'
        }
        
        self.join_patterns = [
            r'(?i)\bJOIN\s+(\w+)',
            r'(?i)\bINNER\s+JOIN\s+(\w+)',
            r'(?i)\bLEFT\s+JOIN\s+(\w+)',
            r'(?i)\bRIGHT\s+JOIN\s+(\w+)',
            r'(?i)\bFULL\s+OUTER\s+JOIN\s+(\w+)',
            r'(?i)\bCROSS\s+JOIN\s+(\w+)'
        ]
    
    def extract_sql_queries(self, plsql_content: str) -> List[SQLQuery]:
        """
        Extract all SQL queries from PL/SQL content
        
        Args:
            plsql_content (str): PL/SQL content
            
        Returns:
            List[SQLQuery]: List of extracted SQL queries
        """
        queries = []
        
        # Split content into lines for line number tracking
        lines = plsql_content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # Skip comments and empty lines
            if line.startswith('--') or line.startswith('/*') or not line:
                continue
            
            # Try to extract different types of SQL queries
            for query_type, pattern in self.sql_patterns.items():
                matches = re.finditer(pattern, line, re.IGNORECASE | re.DOTALL)
                
                for match in matches:
                    query_text = match.group(0).strip()
                    
                    # Parse the query to extract metadata
                    query_info = self._parse_sql_query(query_text, query_type, line_num, line)
                    
                    if query_info:
                        queries.append(query_info)
        
        # Also try to extract multi-line queries
        multiline_queries = self._extract_multiline_queries(plsql_content)
        queries.extend(multiline_queries)
        
        logger.info(f"Extracted {len(queries)} SQL queries from PL/SQL content")
        return queries
    
    def _extract_multiline_queries(self, content: str) -> List[SQLQuery]:
        """Extract multi-line SQL queries"""
        queries = []
        
        # Find blocks that look like SQL statements
        sql_blocks = re.finditer(
            r'(?i)(SELECT|INSERT|UPDATE|DELETE|MERGE).*?(?:;|\n\n|\Z)',
            content,
            re.DOTALL
        )
        
        for match in sql_blocks:
            query_text = match.group(0).strip()
            line_num = content[:match.start()].count('\n') + 1
            
            # Determine query type
            query_type = query_text.split()[0].upper()
            
            # Parse the query
            query_info = self._parse_sql_query(query_text, query_type, line_num, query_text)
            
            if query_info:
                queries.append(query_info)
        
        return queries
    
    def _parse_sql_query(self, query_text: str, query_type: str, 
                        line_number: int, original_context: str) -> Optional[SQLQuery]:
        """
        Parse a SQL query to extract metadata
        
        Args:
            query_text (str): SQL query text
            query_type (str): Type of SQL query
            line_number (int): Line number in original file
            original_context (str): Original context around the query
            
        Returns:
            Optional[SQLQuery]: Parsed query information
        """
        try:
            # Use sqlparse to parse the query
            parsed = sqlparse.parse(query_text)[0]
            
            # Extract tables
            tables = self._extract_tables(parsed)
            
            # Extract columns
            columns = self._extract_columns(parsed, query_type)
            
            # Extract conditions
            conditions = self._extract_conditions(parsed)
            
            # Extract parameters (bind variables)
            parameters = self._extract_parameters(query_text)
            
            return SQLQuery(
                query=query_text,
                query_type=query_type,
                tables=tables,
                columns=columns,
                conditions=conditions,
                parameters=parameters,
                line_number=line_number,
                original_context=original_context
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse SQL query: {str(e)}")
            return None
    
    def _extract_tables(self, parsed: sql.Statement) -> List[str]:
        """Extract table names from parsed SQL"""
        tables = []
        
        def find_tables(token):
            if isinstance(token, sql.Identifier):
                # Check if this looks like a table reference
                if any(keyword in str(token).upper() for keyword in ['FROM', 'JOIN', 'INTO']):
                    table_name = self._clean_identifier(str(token))
                    if table_name and len(table_name) > 1:
                        tables.append(table_name)
            elif hasattr(token, 'tokens'):
                for subtoken in token.tokens:
                    find_tables(subtoken)
        
        for token in parsed.tokens:
            find_tables(token)
        
        return list(set(tables))  # Remove duplicates
    
    def _extract_columns(self, parsed: sql.Statement, query_type: str) -> List[str]:
        """Extract column names from parsed SQL"""
        columns = []
        
        def find_columns(token):
            if isinstance(token, sql.Identifier):
                # Extract column names from SELECT lists, INSERT columns, etc.
                column_text = str(token)
                if '.' in column_text:
                    # Handle table.column format
                    column_name = column_text.split('.')[-1]
                else:
                    column_name = column_text
                
                # Clean up the column name
                column_name = self._clean_identifier(column_name)
                if column_name and len(column_name) > 1:
                    columns.append(column_name)
            elif hasattr(token, 'tokens'):
                for subtoken in token.tokens:
                    find_columns(subtoken)
        
        for token in parsed.tokens:
            find_columns(token)
        
        return list(set(columns))
    
    def _extract_conditions(self, parsed: sql.Statement) -> List[str]:
        """Extract WHERE conditions from parsed SQL"""
        conditions = []
        
        def find_conditions(token):
            if isinstance(token, sql.Where):
                condition_text = str(token).strip()
                if condition_text.startswith('WHERE'):
                    condition_text = condition_text[5:].strip()
                if condition_text:
                    conditions.append(condition_text)
            elif hasattr(token, 'tokens'):
                for subtoken in token.tokens:
                    find_conditions(subtoken)
        
        for token in parsed.tokens:
            find_conditions(token)
        
        return conditions
    
    def _extract_parameters(self, query_text: str) -> List[str]:
        """Extract bind parameters from SQL query"""
        parameters = []
        
        # Look for bind variables (e.g., :param, ?)
        bind_patterns = [
            r':\w+',  # Named parameters like :param_name
            r'\?',    # Positional parameters
            r'@\w+',  # SQL Server style parameters
        ]
        
        for pattern in bind_patterns:
            matches = re.findall(pattern, query_text, re.IGNORECASE)
            parameters.extend(matches)
        
        return list(set(parameters))
    
    def _clean_identifier(self, identifier: str) -> str:
        """Clean up identifier name"""
        # Remove quotes, brackets, and other special characters
        cleaned = re.sub(r'[`"\[\]]', '', identifier)
        cleaned = cleaned.strip()
        return cleaned
    
    def extract_table_relationships(self, queries: List[SQLQuery]) -> Dict[str, List[str]]:
        """
        Extract table relationships from SQL queries
        
        Args:
            queries (List[SQLQuery]): List of SQL queries
            
        Returns:
            Dict[str, List[str]]: Table relationships
        """
        relationships = {}
        
        for query in queries:
            if len(query.tables) > 1:
                # This query involves multiple tables
                for i, table1 in enumerate(query.tables):
                    for j, table2 in enumerate(query.tables):
                        if i != j:
                            if table1 not in relationships:
                                relationships[table1] = []
                            if table2 not in relationships[table1]:
                                relationships[table1].append(table2)
        
        logger.info(f"Extracted {len(relationships)} table relationships")
        return relationships
    
    def extract_data_access_patterns(self, queries: List[SQLQuery]) -> Dict[str, int]:
        """
        Extract data access patterns from SQL queries
        
        Args:
            queries (List[SQLQuery]): List of SQL queries
            
        Returns:
            Dict[str, int]: Access pattern counts
        """
        patterns = {
            'select_count': 0,
            'insert_count': 0,
            'update_count': 0,
            'delete_count': 0,
            'merge_count': 0,
            'join_count': 0,
            'subquery_count': 0
        }
        
        for query in queries:
            patterns[f'{query.query_type.lower()}_count'] += 1
            
            # Check for joins
            if any(join_type in query.query.upper() for join_type in 
                   ['JOIN', 'INNER JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'FULL OUTER JOIN']):
                patterns['join_count'] += 1
            
            # Check for subqueries
            if '(' in query.query and 'SELECT' in query.query.upper():
                patterns['subquery_count'] += 1
        
        return patterns
    
    def validate_sql_syntax(self, query: str) -> bool:
        """
        Validate SQL syntax using sqlparse
        
        Args:
            query (str): SQL query to validate
            
        Returns:
            bool: True if syntax is valid
        """
        try:
            parsed = sqlparse.parse(query)
            return len(parsed) > 0 and parsed[0].tokens
        except:
            return False
    
    def format_sql_query(self, query: str) -> str:
        """
        Format SQL query for better readability
        
        Args:
            query (str): SQL query to format
            
        Returns:
            str: Formatted SQL query
        """
        try:
            return sqlparse.format(
                query,
                reindent=True,
                keyword_case='upper',
                identifier_case='lower'
            )
        except:
            return query


class QueryAnalyzer:
    """Analyzes SQL queries for conversion patterns"""
    
    def __init__(self):
        """Initialize query analyzer"""
        self.conversion_patterns = {
            'cursor_loops': self._analyze_cursor_loops,
            'dynamic_sql': self._analyze_dynamic_sql,
            'bulk_operations': self._analyze_bulk_operations,
            'error_handling': self._analyze_error_handling
        }
    
    def analyze_query_patterns(self, queries: List[SQLQuery]) -> Dict[str, Any]:
        """
        Analyze SQL queries for conversion patterns
        
        Args:
            queries (List[SQLQuery]): List of SQL queries
            
        Returns:
            Dict[str, Any]: Analysis results
        """
        analysis = {
            'total_queries': len(queries),
            'query_types': {},
            'table_usage': {},
            'column_usage': {},
            'patterns': {}
        }
        
        # Count query types
        for query in queries:
            query_type = query.query_type.lower()
            analysis['query_types'][query_type] = analysis['query_types'].get(query_type, 0) + 1
            
            # Track table usage
            for table in query.tables:
                analysis['table_usage'][table] = analysis['table_usage'].get(table, 0) + 1
            
            # Track column usage
            for column in query.columns:
                analysis['column_usage'][column] = analysis['column_usage'].get(column, 0) + 1
        
        # Analyze specific patterns
        for pattern_name, analyzer_func in self.conversion_patterns.items():
            analysis['patterns'][pattern_name] = analyzer_func(queries)
        
        return analysis
    
    def _analyze_cursor_loops(self, queries: List[SQLQuery]) -> Dict[str, Any]:
        """Analyze cursor loop patterns"""
        cursor_loops = []
        
        for query in queries:
            if 'cursor' in query.original_context.lower():
                cursor_loops.append({
                    'query': query.query,
                    'tables': query.tables,
                    'line_number': query.line_number
                })
        
        return {
            'count': len(cursor_loops),
            'queries': cursor_loops
        }
    
    def _analyze_dynamic_sql(self, queries: List[SQLQuery]) -> Dict[str, Any]:
        """Analyze dynamic SQL patterns"""
        dynamic_sql = []
        
        for query in queries:
            if any(param.startswith(':') or param == '?' for param in query.parameters):
                dynamic_sql.append({
                    'query': query.query,
                    'parameters': query.parameters,
                    'line_number': query.line_number
                })
        
        return {
            'count': len(dynamic_sql),
            'queries': dynamic_sql
        }
    
    def _analyze_bulk_operations(self, queries: List[SQLQuery]) -> Dict[str, Any]:
        """Analyze bulk operation patterns"""
        bulk_ops = []
        
        for query in queries:
            if any(keyword in query.query.upper() for keyword in ['BULK COLLECT', 'FORALL']):
                bulk_ops.append({
                    'query': query.query,
                    'type': 'bulk_operation',
                    'line_number': query.line_number
                })
        
        return {
            'count': len(bulk_ops),
            'queries': bulk_ops
        }
    
    def _analyze_error_handling(self, queries: List[SQLQuery]) -> Dict[str, Any]:
        """Analyze error handling patterns"""
        error_handling = []
        
        for query in queries:
            if any(keyword in query.original_context.upper() for keyword in ['EXCEPTION', 'ERROR', 'RAISE']):
                error_handling.append({
                    'query': query.query,
                    'line_number': query.line_number,
                    'context': query.original_context
                })
        
        return {
            'count': len(error_handling),
            'queries': error_handling
        }


def create_sql_extractor() -> SQLExtractor:
    """Create and return a configured SQL extractor"""
    return SQLExtractor()


def create_query_analyzer() -> QueryAnalyzer:
    """Create and return a configured query analyzer"""
    return QueryAnalyzer()