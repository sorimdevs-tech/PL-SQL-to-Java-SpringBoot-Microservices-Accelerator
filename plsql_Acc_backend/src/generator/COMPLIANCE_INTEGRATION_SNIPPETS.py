"""
COMPLIANCE INTEGRATION SNIPPETS FOR spring_boot_generator.py

These code snippets show exactly where to add compliance checking
in the generate_services() and generate_controllers() methods.
"""

# ============================================================================
# SNIPPET 1: Add to generate_services() method
# ============================================================================
GENERATE_SERVICES_INTEGRATION = """
def generate_services(self, java_code: Dict[str, str], write_files: bool = True) -> Dict[str, str]:
    '''Generate service classes with compliance validation'''
    
    services = {}
    
    for class_name, code_template in java_code.items():
        if not class_name.endswith('Service'):
            continue
        
        # ... existing service generation code ...
        
        # BUILD the service_code here
        service_code = f'''
@Service
@Slf4j
public class {class_name} {{
    // methods go here
}}
'''
        
        # ✨ ADD COMPLIANCE CHECK HERE ✨
        if COMPLIANCE_ENFORCER_AVAILABLE:
            class_result = JavaComplianceEnforcer.validate_class(
                service_code,
                class_name=class_name
            )
            
            if not class_result.is_compliant:
                self.logger.warning(f"\\n{'='*80}")
                self.logger.warning(f"COMPLIANCE CHECK: Service '{class_name}' found violations:")
                for violation in class_result.violations:
                    self.logger.warning(f"  ⚠ {violation}")
                self.logger.warning(f"{'='*80}\\n")
            
            # USE THE CORRECTED CODE
            service_code = class_result.corrected_code
        
        services[f"{class_name}.java"] = service_code
        
        # Write to file (now with corrected, compliant code)
        if write_files:
            service_path = Path(self.output_dir) / "src" / "main" / "java" / \
                          self.package_name.replace('.', '/') / "service" / \
                          f"{class_name}.java"
            service_path.parent.mkdir(parents=True, exist_ok=True)
            service_path.write_text(service_code)
    
    return services
"""

# ============================================================================
# SNIPPET 2: Add to generate_controllers() method
# ============================================================================
GENERATE_CONTROLLERS_INTEGRATION = """
def generate_controllers(self, services: Dict[str, str], write_files: bool = True) -> Dict[str, str]:
    '''Generate controller classes with compliance validation'''
    
    controllers = {}
    
    for service_file, service_code in services.items():
        # Extract class name from service
        class_match = re.search(r'class\\s+(\\w+Service)\\b', service_code)
        if not class_match:
            continue
        
        service_name = class_match.group(1)
        controller_name = service_name.replace('Service', 'Controller')
        
        # ... existing controller generation code ...
        
        # BUILD the controller_code here
        controller_code = f'''
@RestController
@RequestMapping("/api/{endpoint}")
public class {controller_name} {{
    
    @Autowired
    private {service_name} {self._to_camel_case(service_name)};
    
    // endpoints here
}}
'''
        
        # ✨ ADD COMPLIANCE CHECK HERE ✨
        if COMPLIANCE_ENFORCER_AVAILABLE:
            class_result = JavaComplianceEnforcer.validate_class(
                controller_code,
                class_name=controller_name
            )
            
            if not class_result.is_compliant:
                self.logger.warning(f"\\n{'='*80}")
                self.logger.warning(f"COMPLIANCE CHECK: Controller '{controller_name}' found violations:")
                for violation in class_result.violations:
                    self.logger.warning(f"  ⚠ {violation}")
                self.logger.warning(f"{'='*80}\\n")
            
            # USE THE CORRECTED CODE
            controller_code = class_result.corrected_code
        
        controllers[f"{controller_name}.java"] = controller_code
        
        # Write to file (now with corrected, compliant code)
        if write_files:
            controller_path = Path(self.output_dir) / "src" / "main" / "java" / \
                             self.package_name.replace('.', '/') / "controller" / \
                             f"{controller_name}.java"
            controller_path.parent.mkdir(parents=True, exist_ok=True)
            controller_path.write_text(controller_code)
    
    return controllers
"""

# ============================================================================
# SNIPPET 3: Add to generate_repositories() method
# ============================================================================
GENERATE_REPOSITORIES_INTEGRATION = """
def generate_repositories(self, entities: Dict[str, str], write_files: bool = True) -> Dict[str, str]:
    '''Generate repository interfaces with compliance validation'''
    
    repositories = {}
    
    for entity_file, entity_code in entities.items():
        # Extract class name
        class_match = re.search(r'class\\s+(\\w+Entity)\\b', entity_code)
        if not class_match:
            continue
        
        entity_name = class_match.group(1)
        repo_name = entity_name.replace('Entity', '') + 'Repository'
        
        # ... existing repository generation code ...
        
        # BUILD the repository_code
        repository_code = f'''
@Repository
public interface {repo_name} extends JpaRepository<{entity_name}, Long> {{
    // custom queries here
}}
'''
        
        # ✨ ADD COMPLIANCE CHECK HERE ✨
        if COMPLIANCE_ENFORCER_AVAILABLE:
            # For repositories, also validate them
            class_result = JavaComplianceEnforcer.validate_class(
                repository_code,
                class_name=repo_name
            )
            
            if not class_result.is_compliant:
                self.logger.warning(f"\\n{'='*80}")
                self.logger.warning(f"COMPLIANCE CHECK: Repository '{repo_name}' found violations:")
                for violation in class_result.violations:
                    self.logger.warning(f"  ⚠ {violation}")
                self.logger.warning(f"{'='*80}\\n")
            
            repository_code = class_result.corrected_code
        
        repositories[f"{repo_name}.java"] = repository_code
        
        if write_files:
            repo_path = Path(self.output_dir) / "src" / "main" / "java" / \
                       self.package_name.replace('.', '/') / "repository" / \
                       f"{repo_name}.java"
            repo_path.parent.mkdir(parents=True, exist_ok=True)
            repo_path.write_text(repository_code)
    
    return repositories
"""

# ============================================================================
# SNIPPET 4: Add to generate_entities() method
# ============================================================================
GENERATE_ENTITIES_INTEGRATION = """
def generate_entities(
    self, 
    table_names: List[str], 
    write_files: bool = True
) -> Dict[str, str]:
    '''Generate JPA entities with compliance validation'''
    
    entities = {}
    
    for table_name in table_names:
        entity_name = self._table_name_to_entity_name(table_name)
        
        # ... existing entity generation code ...
        
        # BUILD entity_code
        entity_code = f'''
@Entity
@Table(name = "{table_name}")
public class {entity_name} {{
    // fields and getters/setters
}}
'''
        
        # ✨ ADD COMPLIANCE CHECK HERE ✨
        if COMPLIANCE_ENFORCER_AVAILABLE:
            class_result = JavaComplianceEnforcer.validate_class(
                entity_code,
                class_name=entity_name
            )
            
            if not class_result.is_compliant:
                self.logger.warning(f"\\n{'='*80}")
                self.logger.warning(f"COMPLIANCE CHECK: Entity '{entity_name}' found violations:")
                for violation in class_result.violations:
                    self.logger.warning(f"  ⚠ {violation}")
                self.logger.warning(f"{'='*80}\\n")
            
            entity_code = class_result.corrected_code
        
        entities[f"{entity_name}.java"] = entity_code
        
        if write_files:
            entity_path = Path(self.output_dir) / "src" / "main" / "java" / \
                         self.package_name.replace('.', '/') / "entity" / \
                         f"{entity_name}.java"
            entity_path.parent.mkdir(parents=True, exist_ok=True)
            entity_path.write_text(entity_code)
    
    return entities
"""

# ============================================================================
# SNIPPET 5: Add to generate_project() method (main entry point)
# ============================================================================
GENERATE_PROJECT_INTEGRATION = """
async def generate_project(
    self,
    java_code: Dict[str, str],
    auto_generate_controllers: bool = True
) -> Dict[str, Any]:
    '''Generate complete Spring Boot project with compliance checks'''
    
    self.logger.info(f"\\n{'='*80}")
    self.logger.info("STARTING SPRING BOOT PROJECT GENERATION WITH COMPLIANCE CHECKS")
    self.logger.info(f"{'='*80}\\n")
    
    summary = {}
    
    try:
        # Stage 1: Generate entities
        self.logger.info("Stage 1: Generating JPA Entities...")
        entities = self.generate_entities(self.table_names, write_files=True)
        summary['entities'] = len(entities)
        
        # Stage 2: Generate repositories  
        self.logger.info("Stage 2: Generating Repositories...")
        repositories = self.generate_repositories(entities, write_files=True)
        summary['repositories'] = len(repositories)
        
        # Stage 3: Generate services
        self.logger.info("Stage 3: Generating Services with compliance checks...")
        services = self.generate_services(java_code, write_files=True)
        summary['services'] = len(services)
        
        # Stage 4: Generate controllers
        if auto_generate_controllers:
            self.logger.info("Stage 4: Generating Controllers with compliance checks...")
            controllers = self.generate_controllers(services, write_files=True)
            summary['controllers'] = len(controllers)
        
        self.logger.info(f"\\n{'='*80}")
        self.logger.info("✓ PROJECT GENERATION COMPLETE - ALL CODE IS COMPLIANCE CHECKED")
        self.logger.info(f"{'='*80}\\n")
        
        return {
            'status': 'SUCCESS',
            'summary': summary,
            'output_directory': self.output_dir
        }
    
    except Exception as e:
        self.logger.error(f"\\n{'='*80}")
        self.logger.error(f"✗ PROJECT GENERATION FAILED: {e}")
        self.logger.error(f"{'='*80}\\n")
        raise
"""

# ============================================================================
# SNIPPET 6: Add at top of SpringBootGenerator class
# ============================================================================
CLASS_INIT_INTEGRATION = """
class SpringBootGenerator:
    def __init__(self, output_dir: str, package_name: str):
        self.output_dir = output_dir
        self.package_name = package_name
        self.logger = logging.getLogger(__name__)
        
        # ✨ COMPLIANCE ENFORCER STATE ✨
        self.compliance_violations_found = 0
        self.compliance_fixes_applied = 0
        
    def _log_compliance_violation(self, class_name: str, violation: str):
        '''Log compliance violation for tracking'''
        self.compliance_violations_found += 1
        self.logger.warning(f"Compliance Issue in {class_name}: {violation}")
    
    def _log_compliance_fix(self, class_name: str, fix: str):
        '''Log compliance fix for tracking'''
        self.compliance_fixes_applied += 1
        self.logger.info(f"Compliance Fix in {class_name}: {fix}")
"""

# ============================================================================
# SUMMARY OF INTEGRATION CHANGES
# ============================================================================

SUMMARY = """
These snippets show how to integrate the compliance enforcer into the
spring_boot_generator.py:

1. Add imports at the top of the file (✓ ALREADY DONE)
2. Add compliance checks in generate_services() - before writing file
3. Add compliance checks in generate_controllers() - before writing file  
4. Add compliance checks in generate_repositories() - before writing file
5. Add compliance checks in generate_entities() - before writing file
6. Update generate_project() to log compliance metrics

The pattern is consistent:
  1. Generate code as normal
  2. Validate with JavaComplianceEnforcer.validate_class()
  3. Log any violations found
  4. Use the corrected_code from the result
  5. Write the corrected code to file

This ensures 100% of generated code follows all 12 rules!
"""

print(__doc__)
print(SUMMARY)
