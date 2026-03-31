"""
Table Metadata Provider - Enhanced Entity Schema Synchronization

This module provides comprehensive table schema information to ensure:
1. All discovered columns are available to LLM prompts
2. Entities are generated with complete field sets
3. Services reference only fields that exist in entities
4. Spring Data repository methods are generated with correct signatures
"""

from typing import Dict, List, Set, Any, Optional, Tuple
from dataclasses import dataclass, field
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class ColumnMetadata:
    """Represents a table column with complete type information"""
    name: str  # Column name (e.g., "BOOKID")
    sql_type: str  # SQL type (e.g., "VARCHAR2(50)", "NUMBER(10,2)")
    java_type: str  # Mapped Java type (e.g., "String", "BigDecimal")
    is_pk: bool = False
    is_fk: bool = False
    nullable: bool = True
    precision: int = 0  # For NUMBER types
    scale: int = 0  # For NUMBER types
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template formatting"""
        return {
            "name": self.name,
            "sql_type": self.sql_type,
            "java_type": self.java_type,
            "is_pk": self.is_pk,
            "is_fk": self.is_fk,
            "java_field_name": self._get_java_field_name(),
            "java_getter": f"get{self._to_pascal_case(self._get_java_field_name())}",
            "java_setter": f"set{self._to_pascal_case(self._get_java_field_name())}",
        }
    
    @staticmethod
    def _to_pascal_case(snake_case: str) -> str:
        """Convert SNAKE_CASE to PascalCase"""
        return "".join(word.capitalize() for word in snake_case.split("_"))
    
    def _get_java_field_name(self) -> str:
        """Get camelCase Java field name from SQL column name"""
        # Convert BOOKID -> bookid -> bookId (but actually lowercase first word)
        parts = self.name.lower().split("_")
        if not parts:
            return self.name.lower()
        return parts[0] + "".join(p.capitalize() for p in parts[1:])


@dataclass
class TableMetadata:
    """Complete schema information for a table"""
    table_name: str  # SQL table name (uppercase)
    java_entity_name: str  # Corresponding Java entity class name
    columns: List[ColumnMetadata] = field(default_factory=list)
    primary_keys: List[str] = field(default_factory=list)
    foreign_keys: Dict[str, str] = field(default_factory=dict)  # fk_column -> ref_table
    alternative_names: List[str] = field(default_factory=list)  # Common name variations
    
    def get_column(self, name: str) -> Optional[ColumnMetadata]:
        """Find column by name (case-insensitive)"""
        name_upper = name.upper()
        for col in self.columns:
            if col.name == name_upper:
                return col
        return None
    
    def get_columns_for_select(self) -> List[ColumnMetadata]:
        """Get all columns that can be selected"""
        return [col for col in self.columns if not col.is_fk or col.is_pk]
    
    def get_columns_for_insert(self) -> List[ColumnMetadata]:
        """Get all columns that can be inserted (excluding auto-generated PKs, FKs handled separately)"""
        return [col for col in self.columns if not (col.is_pk and not re.match(r"ID$", col.name))]
    
    def get_columns_for_update(self) -> List[ColumnMetadata]:
        """Get all columns that can be updated (excluding PKs)"""
        return [col for col in self.columns if not col.is_pk]
    
    def to_dict_for_prompt(self) -> Dict[str, Any]:
        """Convert to format suitable for LLM prompts"""
        return {
            "table_name": self.table_name,
            "entity_name": self.java_entity_name,
            "columns": [col.to_dict() for col in self.columns],
            "primary_keys": self.primary_keys,
            "foreign_keys": self.foreign_keys,
            "column_list": ", ".join(col.name for col in self.columns),
            "selector_list": ", ".join(f"get{col.to_dict()['java_getter'].replace('get', '')}" for col in self.columns),
        }


class TableMetadataProvider:
    """
    Provider for comprehensive table metadata
    
    Ensures:
    - All discovered columns are available to services
    - Entity schemas are complete and synchronized
    - LLM prompts have accurate field information
    """
    
    def __init__(self):
        self.tables: Dict[str, TableMetadata] = {}  # table_name -> TableMetadata
        self.entity_to_table: Dict[str, str] = {}  # entity_name -> table_name
        self._sql_to_java_type_map = self._build_type_map()
    
    @staticmethod
    def _build_type_map() -> Dict[str, str]:
        """Map SQL types to Java types"""
        return {
            "VARCHAR2": "String",
            "VARCHAR": "String",
            "CHAR": "String",
            "NVARCHAR2": "String",
            "NUMBER": "BigDecimal",
            "INTEGER": "Long",
            "INT": "Long",
            "SMALLINT": "Long",
            "FLOAT": "Double",
            "DATE": "LocalDateTime",
            "TIMESTAMP": "LocalDateTime",
            "TIMESTAMP WITH TIME ZONE": "LocalDateTime",
            "TIMESTAMP WITH LOCAL TIME ZONE": "LocalDateTime",
            "BOOLEAN": "Boolean",
            "CLOB": "String",
            "BLOB": "byte[]",
            "RAW": "byte[]",
            "LONG": "String",
        }
    
    def register_table(self, table_name: str, entity_name: str, 
                      columns_dict: Dict[str, str]) -> TableMetadata:
        """
        Register a discovered table with its columns
        
        Args:
            table_name: SQL table name (will be uppercased)
            entity_name: Java entity class name
            columns_dict: Dict mapping column_name -> sql_type
        
        Returns:
            TableMetadata object
        """
        table_name_upper = table_name.upper()
        
        # Parse columns
        columns_list: List[ColumnMetadata] = []
        for col_name, sql_type in columns_dict.items():
            col_name_upper = col_name.upper()
            
            # Extract Java type
            java_type = self._map_sql_type_to_java(sql_type)
            
            # Parse precision and scale for NUMBER types
            precision, scale = self._parse_number_type(sql_type)
            
            # Determine if it's likely a primary key
            is_pk = col_name_upper in ["ID", "PK"] or col_name_upper.endswith("_ID") and col_name_upper.startswith("PK_")
            
            col_meta = ColumnMetadata(
                name=col_name_upper,
                sql_type=sql_type.upper(),
                java_type=java_type,
                is_pk=is_pk,
                is_fk=False,
                precision=precision,
                scale=scale,
            )
            columns_list.append(col_meta)
        
        # Create metadata
        metadata = TableMetadata(
            table_name=table_name_upper,
            java_entity_name=entity_name,
            columns=columns_list,
        )
        
        # Register
        self.tables[table_name_upper] = metadata
        self.entity_to_table[entity_name] = table_name_upper
        
        logger.info(f"Registered table {table_name_upper} with entity {entity_name}: {len(columns_list)} columns")
        return metadata
    
    def get_table_metadata(self, table_name_or_entity: str) -> Optional[TableMetadata]:
        """Get table metadata by table name or entity name"""
        # Try as table name first
        table_name_upper = table_name_or_entity.upper()
        if table_name_upper in self.tables:
            return self.tables[table_name_upper]
        
        # Try as entity name
        if table_name_or_entity in self.entity_to_table:
            mapped_table = self.entity_to_table[table_name_or_entity]
            return self.tables.get(mapped_table)
        
        return None
    
    def get_entity_fields_for_service_prompt(self, entity_name: str) -> str:
        """
        Get formatted entity fields for LLM prompts
        
        Format:
        EntityName: fieldName (type), anotherField (type)
        """
        metadata = self.get_table_metadata(entity_name)
        if not metadata:
            return f"{entity_name}: (schema not available)"
        
        fields = []
        for col in metadata.columns:
            field_name = col.to_dict()["java_field_name"]
            fields.append(f"{field_name} ({col.java_type})")
        
        return f"{entity_name}: {', '.join(fields)}"
    
    def get_all_entity_fields_text(self) -> str:
        """Get all entity fields formatted for prompts"""
        if not self.tables:
            return "(none — internal schema not available)"
        
        lines = []
        for table_meta in self.tables.values():
            lines.append(self.get_entity_fields_for_service_prompt(table_meta.java_entity_name))
        
        return "\n".join(lines) if lines else "(none)"
    
    def get_repository_method_stubs(self, entity_name: str) -> str:
        """
        Generate example repository method stubs for this entity
        
        Useful for LLM prompts to show valid signatures
        """
        metadata = self.get_table_metadata(entity_name)
        if not metadata:
            return f"// {entity_name} schema not available"
        
        lines = [f"// Generated method stubs for {metadata.java_entity_name}"]
        
        # Find PK column
        pk_col = None
        for col in metadata.columns:
            if col.is_pk:
                pk_col = col
                break
        
        if pk_col:
            pk_type = pk_col.java_type
            pk_java_name = pk_col.to_dict()["java_field_name"]
            lines.append(f"Optional<{entity_name}> findById({pk_type} {pk_java_name});")
            lines.append(f"void deleteById({pk_type} {pk_java_name});")
        
        # Insert method for all non-PK columns
        insert_params = []
        for col in metadata.columns:
            if not col.is_pk:
                java_name = col.to_dict()["java_field_name"]
                insert_params.append(f"{col.java_type} {java_name}")
        
        if insert_params:
            insert_sig = f"int insert{entity_name}({', '.join(insert_params)});"
            lines.append(insert_sig)
        
        return "\n".join(lines)
    
    def _map_sql_type_to_java(self, sql_type: str) -> str:
        """Map SQL type string to Java type"""
        sql_upper = sql_type.upper()
        
        # Extract base type (remove precision/scale)
        base_type = re.sub(r'\(.*\)', '', sql_upper).strip()
        
        # Check for common patterns
        if base_type.startswith("NUMBER"):
            # Check if it has decimal places
            match = re.search(r'NUMBER\s*\(\s*\d+\s*,\s*(\d+)\s*\)', sql_upper)
            if match and int(match.group(1)) > 0:
                return "BigDecimal"
            return "Long"
        
        # Direct mapping
        for sql_pat, java_type in self._sql_to_java_type_map.items():
            if base_type.startswith(sql_pat):
                return java_type
        
        # Default to String if unknown
        logger.warning(f"Unknown SQL type: {sql_type}, defaulting to String")
        return "String"
    
    @staticmethod
    def _parse_number_type(sql_type: str) -> Tuple[int, int]:
        """Parse NUMBER(precision,scale) to extract precision and scale"""
        match = re.search(r'NUMBER\s*\(\s*(\d+)\s*(?:,\s*(\d+))?\s*\)', sql_type.upper())
        if match:
            precision = int(match.group(1))
            scale = int(match.group(2)) if match.group(2) else 0
            return precision, scale
        return 0, 0
    
    def export_for_prompt_context(self) -> Dict[str, Any]:
        """Export all metadata in format suitable for LLM prompts"""
        return {
            "entity_fields": self.get_all_entity_fields_text(),
            "entity_count": len(self.tables),
            "all_tables": {
                table_name: meta.to_dict_for_prompt()
                for table_name, meta in self.tables.items()
            },
            "repository_examples": "\n\n".join(
                self.get_repository_method_stubs(meta.java_entity_name)
                for meta in self.tables.values()
            ),
        }
