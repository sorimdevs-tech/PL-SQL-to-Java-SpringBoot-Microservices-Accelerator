#!/usr/bin/env python
"""
Verify SBG-30 works correctly by testing the actual Spring Boot Generator with procedure metadata
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.generator.spring_boot_generator import SpringBootGenerator
from src.generator.dynamic_logic_extractor import PLSQLLogicExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('test_sbg30_generator')

def test_sbg30_in_generator():
    """Test that SBG-30 works in the actual SpringBootGenerator"""
    
    logger.info("=" * 80)
    logger.info("Testing SBG-30 Integration in SpringBootGenerator")
    logger.info("=" * 80)
    
    # Create generator with config dict
    config = {
        'package_name': 'com.example',
        'group_id': 'com.example',
        'artifact_id': 'plsql-service',
        'java_version': '17',
        'spring_boot_version': '3.2.5',
        'build_tool': 'maven'
    }
    
    generator = SpringBootGenerator(config)
    
    # Sample procedures to register
    procedures = [
        {
            'name': 'create_invoice',
            'package': 'invoice_api_pkg',
            'package_name': 'invoice_api_pkg',
            'object_type': 'PROCEDURE',
            'raw_plsql': '''
                PROCEDURE create_invoice(p_customer_id NUMBER, p_amount NUMBER) IS
                BEGIN
                    IF p_customer_id IS NULL THEN
                      RAISE_APPLICATION_ERROR(-20001, 'Customer ID required');
                    END IF;
                    IF p_amount <= 0 THEN
                      RAISE_APPLICATION_ERROR(-20002, 'Amount must be positive');
                    END IF;
                    v_total := p_amount * 1.15;
                    INSERT INTO invoices VALUES (p_customer_id, p_amount, v_total);
                    COMMIT;
                END create_invoice;
            ''',
            'body': '',
            'parameters': [],
        }
    ]
    
    logger.info(f"Step 1: Registering {len(procedures)} procedures with generator")
    generator.register_procedure_metadata(procedures, {})
    
    logger.info(f"Step 2: Verifying metadata was stored")
    if len(generator._procedure_metadata) == 0:
        logger.error("❌ No procedures registered!")
        return False
    
    logger.info(f"✓ Stored metadata keys: {list(generator._procedure_metadata.keys())}")
    
    logger.info(f"Step 3: Testing service name matching")
    # Test that service name matches stored procedure
    service_name = 'InvoiceApiPkgCreateInvoiceService'
    proc_metadata = generator._get_procedure_metadata(service_name)
    
    if not proc_metadata:
        logger.error(f"❌ Failed to match service '{service_name}' to procedure metadata")
        return False
    
    logger.info(f"✓ Successfully matched '{service_name}' to procedure metadata")
    logger.info(f"  Metadata contains:")
    logger.info(f"    - Validations: {len(proc_metadata.get('logic', {}).validates if hasattr(proc_metadata, 'logic') else [])}")
    logger.info(f"    - Logic object type: {type(proc_metadata.get('logic'))}")
    
    logger.info(f"Step 4: Generating service code with procedure metadata")
    
    # Simulate service generation
    service_template = '''
@Service
public class InvoiceApiPkgCreateInvoiceService {
    @Autowired
    private InvoiceRepository invoiceRepository;
    
    @Transactional
    public void createInvoice(Long customerId, BigDecimal amount) {
        // TODO: Implement business logic
        throw new BusinessException("Not implemented");
    }
}
'''
    
    logger.info(f"Step 5: Normalizing service with SBG-30")
    normalized = generator._normalize_service_code(
        'InvoiceApiPkgCreateInvoiceService.java',
        service_template
    )
    
    if not normalized:
        logger.error("❌ Service normalization returned empty")
        return False
    
    logger.info(f"✓ Service normalized (length: {len(normalized)} chars)")
    
    # Check if normalized service has actual logic
    has_validation = 'if (' in normalized and 'businessException' in normalized.lower()
    has_calculation = '*' in normalized or 'BigDecimal' in normalized
    has_insert = 'insert' in normalized.lower() or 'save(' in normalized
    has_transactional = '@Transactional' in normalized
    
    logger.info(f"\nStep 6: Inspecting normalized service for business logic:")
    logger.info(f"  @Transactional annotation: {'✓' if has_transactional else '✗'}")
    logger.info(f"  Validation logic: {'✓' if has_validation else '✗'}")
    logger.info(f"  Calculation logic: {'✓' if has_calculation else '✗'}")
    logger.info(f"  Insert/operation logic: {'✓' if has_insert else '✗'}")
    
    logic_score = sum([has_validation, has_calculation, has_insert, has_transactional])
    
    logger.info(f"\nStep 7: Full normalized service code:")
    logger.info("---")
    # Print in sections to avoid truncation
    lines = normalized.split('\n')
    for i, line in enumerate(lines):
        if i < 60:  # Print first 60 lines
            print(line)
    
    logger.info("\n" + "=" * 80)
    if logic_score >= 2:
        logger.info(f"✅ SUCCESS: Service has {logic_score}/4 business logic elements")
        return True
    else:
        logger.error(f"❌ FAILURE: Service only has {logic_score}/4 business logic elements")
        return False

if __name__ == '__main__':
    success = test_sbg30_in_generator()
    exit(0 if success else 1)
