"""
Enhanced LLM Conversion Engine Integration

This module enhances the LLM engine to use:
1. Table metadata for complete entity schemas
2. Spring Data best practices
3. Improved PL/SQL logic extraction
"""

from typing import Dict, Any, Optional, List
import logging
import re

logger = logging.getLogger(__name__)


class MetadataAwareLLMEngine:
    """
    Wrapper around LLM engine that injects metadata and enhanced prompts
    """
    
    def __init__(self, base_llm_engine, metadata_provider=None):
        """
        Initialize with base LLM engine and optional metadata provider
        
        Args:
            base_llm_engine: The existing LLMConversionEngine instance
            metadata_provider: Optional TableMetadataProvider instance
        """
        self.base_engine = base_llm_engine
        self.metadata_provider = metadata_provider
        self.prompt_template = base_llm_engine.prompt_template
    
    def enhance_context_with_metadata(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance context dict with metadata provider information
        
        Args:
            context: Existing context dictionary
        
        Returns:
            Enhanced context with metadata fields
        """
        if not self.metadata_provider:
            return context
        
        enhanced = dict(context)
        
        # Add repository method examples
        repo_examples = self._generate_repository_examples()
        if repo_examples:
            enhanced['repository_examples'] = repo_examples
        
        # Add Spring Data patterns
        enhanced['spring_data_patterns'] = self._get_spring_data_guidance()
        
        # Add entity field constraints
        entity_fields_text = self.metadata_provider.get_all_entity_fields_text()
        enhanced['entity_fields'] = entity_fields_text
        
        logger.info("Enhanced context with metadata from TableMetadataProvider")
        return enhanced
    
    def _generate_repository_examples(self) -> str:
        """Generate repository method examples from metadata"""
        examples = []
        
        if not self.metadata_provider or not self.metadata_provider.tables:
            return ""
        
        for table_meta in list(self.metadata_provider.tables.values())[:3]:  # First 3 entities
            entity_name = table_meta.java_entity_name
            examples.append(f"// {entity_name}")
            
            # Find PK
            for col in table_meta.columns:
                if col.is_pk:
                    java_name = col.to_dict()["java_field_name"]
                    examples.append(f"Optional<{entity_name}> findById({col.java_type} {java_name});")
                    examples.append(f"void deleteById({col.java_type} {java_name});")
                    break
            
            # Add insert method for non-PK columns
            insert_params = []
            for col in table_meta.columns:
                if not col.is_pk:
                    java_name = col.to_dict()["java_field_name"]
                    insert_params.append(f"{col.java_type} {java_name}")
            
            if insert_params:
                param_list = ", ".join(insert_params[:5])  # Limit to 5 params
                examples.append(f"int insert{entity_name}({param_list});")
            
            examples.append("")
        
        return "\n".join(examples)
    
    @staticmethod
    def _get_spring_data_guidance() -> str:
        """Get Spring Data best practices guidance"""
        return """
=== SPRING DATA REPOSITORY PATTERNS ===

✓ CORRECT: findById returns Optional
  Optional<Entity> entity = repository.findById(id);
  Entity e = entity.orElseThrow(() -> new Exception(...));

✓ CORRECT: Use save() for INSERT and UPDATE
  Entity e = new Entity();
  e.setField(value);
  repository.save(e);

✓ CORRECT: Use deleteById() for DELETE
  repository.deleteById(id);

✗ WRONG: These methods don't exist in Spring Data
  repository.findOne(...)  // Use findById() instead
  repository.update(...)   // Use save() after fetching and modifying
  repository.remove(...)   // Use deleteById() instead

=== ENTITY FIELD ACCESS ===

✓ CORRECT: Only access fields that exist in entity
  entity.setBookid(value);      // If bookid exists in entity
  entity.getPrice();             // If price exists in entity

✗ WRONG: Accessing non-existent fields
  entity.setVideoid(value);     // If videoid NOT defined in entity
  entity.getCardid();           // If cardid NOT defined in entity
"""


class PLSQLLogicExtractor:
    """
    Enhanced PL/SQL logic extraction to generate better Java code
    """
    
    @staticmethod
    def extract_logic_patterns(plsql_code: str) -> Dict[str, Any]:
        """
        Extract PL/SQL logic patterns for better Java generation
        
        Args:
            plsql_code: Raw PL/SQL procedure/function code
        
        Returns:
            Dictionary of extracted patterns
        """
        patterns = {
            "cursor_operations": PLSQLLogicExtractor._extract_cursor_patterns(plsql_code),
            "insert_operations": PLSQLLogicExtractor._extract_insert_patterns(plsql_code),
            "update_operations": PLSQLLogicExtractor._extract_update_patterns(plsql_code),
            "delete_operations": PLSQLLogicExtractor._extract_delete_patterns(plsql_code),
            "conditional_logic": PLSQLLogicExtractor._extract_conditions(plsql_code),
            "loops": PLSQLLogicExtractor._extract_loops(plsql_code),
            "exceptions": PLSQLLogicExtractor._extract_exception_handling(plsql_code),
            "cursor_fetches": PLSQLLogicExtractor._extract_cursor_fetches(plsql_code),
        }
        
        return patterns
    
    @staticmethod
    def _extract_cursor_patterns(plsql_code: str) -> List[Dict[str, str]]:
        """Extract FOR cursor IN ... LOOP patterns"""
        patterns = []
        
        # Pattern: FOR row IN cursor LOOP ... END LOOP;
        cursor_pattern = re.compile(
            r'for\s+(\w+)\s+in\s+(\w+)\s*\(\s*([^)]*)\s*\)\s*(?:loop|LOOP)',
            re.IGNORECASE
        )
        
        for match in cursor_pattern.finditer(plsql_code):
            patterns.append({
                "type": "cursor_loop",
                "row_variable": match.group(1),
                "cursor_name": match.group(2),
                "cursor_params": match.group(3),
            })
        
        return patterns
    
    @staticmethod
    def _extract_insert_patterns(plsql_code: str) -> List[Dict[str, str]]:
        """Extract INSERT statements"""
        patterns = []
        
        # Pattern: INSERT INTO table_name ...
        insert_pattern = re.compile(
            r'insert\s+into\s+(\w+)\s*\((.*?)\)\s*values\s*\((.*?)\)',
            re.IGNORECASE | re.DOTALL
        )
        
        for match in insert_pattern.finditer(plsql_code):
            patterns.append({
                "type": "insert",
                "table": match.group(1).upper(),
                "columns": [c.strip() for c in match.group(2).split(',')],
                "values": [v.strip() for v in match.group(3).split(',')],
            })
        
        return patterns
    
    @staticmethod
    def _extract_update_patterns(plsql_code: str) -> List[Dict[str, str]]:
        """Extract UPDATE statements"""
        patterns = []
        
        # Pattern: UPDATE table_name SET ... WHERE ...
        update_pattern = re.compile(
            r'update\s+(\w+)\s+set\s+(.*?)\s+where\s+(.*?)(?:;|:\w+|$)',
            re.IGNORECASE | re.DOTALL
        )
        
        for match in update_pattern.finditer(plsql_code):
            patterns.append({
                "type": "update",
                "table": match.group(1).upper(),
                "set_clause": match.group(2).strip(),
                "where_clause": match.group(3).strip(),
            })
        
        return patterns
    
    @staticmethod
    def _extract_delete_patterns(plsql_code: str) -> List[Dict[str, str]]:
        """Extract DELETE statements"""
        patterns = []
        
        # Pattern: DELETE FROM table_name WHERE ...
        delete_pattern = re.compile(
            r'delete\s+from\s+(\w+)\s+where\s+(.*?)(?:;|$)',
            re.IGNORECASE | re.DOTALL
        )
        
        for match in delete_pattern.finditer(plsql_code):
            patterns.append({
                "type": "delete",
                "table": match.group(1).upper(),
                "where_clause": match.group(2).strip(),
            })
        
        return patterns
    
    @staticmethod
    def _extract_conditions(plsql_code: str) -> List[Dict[str, str]]:
        """Extract IF/THEN/ELSE logic"""
        patterns = []
        
        # Pattern: IF condition THEN ... ELSE ... END IF;
        if_pattern = re.compile(
            r'if\s+(.*?)\s+then',
            re.IGNORECASE
        )
        
        for match in if_pattern.finditer(plsql_code):
            patterns.append({
                "type": "conditional",
                "condition": match.group(1).strip(),
            })
        
        return patterns
    
    @staticmethod
    def _extract_loops(plsql_code: str) -> List[Dict[str, str]]:
        """Extract WHILE/FOR/LOOP patterns"""
        patterns = []
        
        # Pattern: WHILE condition LOOP ... END LOOP;
        while_pattern = re.compile(
            r'while\s+(.*?)\s+(?:loop|LOOP)',
            re.IGNORECASE
        )
        
        for match in while_pattern.finditer(plsql_code):
            patterns.append({
                "type": "while_loop",
                "condition": match.group(1).strip(),
            })
        
        return patterns
    
    @staticmethod
    def _extract_exception_handling(plsql_code: str) -> List[Dict[str, str]]:
        """Extract EXCEPTION handling blocks"""
        patterns = []
        
        # Pattern: EXCEPTION WHEN ... THEN ...
        exception_pattern = re.compile(
            r'exception\s+when\s+(\w+)\s+then\s+(.*?)(?:when|end)',
            re.IGNORECASE | re.DOTALL
        )
        
        for match in exception_pattern.finditer(plsql_code):
            patterns.append({
                "type": "exception_handler",
                "exception_type": match.group(1).strip(),
                "handler_code": match.group(2).strip()[:100],
            })
        
        return patterns
    
    @staticmethod
    def _extract_cursor_fetches(plsql_code: str) -> List[Dict[str, str]]:
        """Extract FETCH patterns to identify row variable usage"""
        patterns = []
        
        # Pattern: FETCH cursor INTO variable
        fetch_pattern = re.compile(
            r'fetch\s+(\w+)\s+into\s+(.*?)(?:;|\n)',
            re.IGNORECASE
        )
        
        for match in fetch_pattern.finditer(plsql_code):
            patterns.append({
                "type": "cursor_fetch",
                "cursor": match.group(1).strip(),
                "variables": [v.strip() for v in match.group(2).split(',')],
            })
        
        return patterns
    
    @staticmethod
    def generate_pattern_guidance(patterns: Dict[str, List[Dict[str, str]]]) -> str:
        """
        Generate LLM guidance based on extracted patterns
        
        Args:
            patterns: Dictionary of extracted PL/SQL patterns
        
        Returns:
            String guidance for LLM
        """
        guidance_lines = [
            "=== DETECTED PL/SQL PATTERNS ===\n"
        ]
        
        # Cursor loops detected
        if patterns.get("cursor_operations"):
            guidance_lines.append("Detected: FOR...IN...LOOP pattern")
            guidance_lines.append("  → In Java: Use repository.findAll() or findById() + loop")
            guidance_lines.append("  → Iterate using for-each on List or Optional")
        
        # INSERT detected
        if patterns.get("insert_operations"):
            guidance_lines.append("Detected: INSERT statement")
            guidance_lines.append("  → In Java: Create entity, call repository.save(entity)")
            guidance_lines.append("  → OR use custom insertXxx() repository method if available")
        
        # UPDATE detected
        if patterns.get("update_operations"):
            guidance_lines.append("Detected: UPDATE statement")
            guidance_lines.append("  → In Java: findById() → modify fields → save()")
            guidance_lines.append("  → Do NOT use generic update() method (doesn't exist in Spring Data)")
        
        # DELETE detected
        if patterns.get("delete_operations"):
            guidance_lines.append("Detected: DELETE statement")
            guidance_lines.append("  → In Java: Use repository.deleteById(id)")
        
        # Conditionals detected
        if patterns.get("conditional_logic"):
            guidance_lines.append("Detected: IF/THEN/ELSE logic")
            guidance_lines.append("  → In Java: Convert to if/else statements")
        
        # Exception handling detected
        if patterns.get("exceptions"):
            guidance_lines.append("Detected: EXCEPTION handling")
            guidance_lines.append("  → In Java: Use try/catch with BusinessException")
        
        return "\n".join(guidance_lines) if len(guidance_lines) > 1 else ""


def inject_enhanced_prompts(prompt_template, plsql_ast: Dict[str, Any], 
                           context: Dict[str, Any],
                           metadata_provider=None) -> str:
    """
    Inject enhanced prompts with metadata and logic patterns
    
    Args:
        prompt_template: PromptTemplate instance
        plsql_ast: PL/SQL AST
        context: Context dictionary
        metadata_provider: Optional TableMetadataProvider
    
    Returns:
        Enhanced prompt text
    """
    # Extract PL/SQL logic patterns
    plsql_code = context.get('plsql_code', '')
    logic_patterns = PLSQLLogicExtractor.extract_logic_patterns(plsql_code)
    pattern_guidance = PLSQLLogicExtractor.generate_pattern_guidance(logic_patterns)
    
    # Add pattern guidance to context
    enhanced_context = dict(context)
    enhanced_context['plsql_pattern_guidance'] = pattern_guidance
    
    # Add Spring Data patterns to defaults
    enhanced_context.setdefault('spring_data_patterns', 
                               "See repository method examples section below")
    
    # If metadata provider available, add entity contracts
    if metadata_provider:
        gui_engine = MetadataAwareLLMEngine(None, metadata_provider)
        enhanced_context = gui_engine.enhance_context_with_metadata(enhanced_context)
    
    # Get base prompt
    conversion_type = context.get('conversion_type', 'procedure_to_service')
    base_prompt = prompt_template.get_prompt(conversion_type, plsql_ast, enhanced_context)
    
    # Inject pattern guidance into prompt if present
    if pattern_guidance and 'PL/SQL Procedure:' in base_prompt:
        # Insert pattern guidance after PL/SQL code section
        insertion_point = base_prompt.find('\nRequirements:')
        if insertion_point > 0:
            base_prompt = (base_prompt[:insertion_point] + 
                          f"\n\n{pattern_guidance}" + 
                          base_prompt[insertion_point:])
    
    return base_prompt
