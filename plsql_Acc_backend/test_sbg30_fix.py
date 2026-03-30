#!/usr/bin/env python
"""
Test script to verify SBG-30 procedure metadata matching fix
"""
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_sbg30')

def test_procedure_name_matching():
    """Test that service names are correctly matched to procedure names"""
    
    # Simulated stored procedure metadata keys (from semantic model)
    stored_keys = [
        'invoice_api_pkg.create_invoice',
        'invoice_api_pkg.cancel_invoice',
        'customer_pkg.new_customer',
        'customer_pkg.update_customer',
        'paypal_util_pkg.create_payment',
        'xtp.add_string_to_clob',
        'appl_log.write_log',
    ]
    
    # Service names that will arrive at normalization
    test_service_names = [
        'InvoiceApiPkgCreateInvoiceService',
        'InvoiceApiPkgCancelInvoiceService',
        'CustomerPkgNewCustomerService',
        'CustomerPkgUpdateCustomerService',
        'PaypalUtilPkgCreatePaymentService',
        'XtpAddStringToClobService',
        'ApplLogWriteLogService',
    ]
    
    expected_matches = {
        'InvoiceApiPkgCreateInvoiceService': 'invoice_api_pkg.create_invoice',
        'InvoiceApiPkgCancelInvoiceService': 'invoice_api_pkg.cancel_invoice',
        'CustomerPkgNewCustomerService': 'customer_pkg.new_customer',
        'CustomerPkgUpdateCustomerService': 'customer_pkg.update_customer',
        'PaypalUtilPkgCreatePaymentService': 'paypal_util_pkg.create_payment',
        'XtpAddStringToClobService': 'xtp.add_string_to_clob',
        'ApplLogWriteLogService': 'appl_log.write_log',
    }
    
    logger.info(f"Testing procedure metadata matching with {len(stored_keys)} stored keys")
    logger.info(f"Stored keys: {stored_keys}")
    logger.info("=" * 80)
    
    passed = 0
    failed = 0
    
    for service_name in test_service_names:
        logger.info(f"\n[Test] Service: '{service_name}'")
        
        # Simulate the matching logic from _get_procedure_metadata
        base = service_name.replace('Service', '')
        logger.info(f"  Base name: '{base}'")
        
        # Generate variations
        variations = []
        
        # 1. Direct lowercase
        variations.append(base.lower())
        
        # 2. Convert CamelCase to snake_case
        camel_to_snake = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', base)
        camel_to_snake = re.sub('([a-z0-9])([A-Z])', r'\1_\2', camel_to_snake).lower()
        variations.append(camel_to_snake)
        
        # 3. Extract parts after 'Pkg' keyword
        if 'Pkg' in base:
            after_pkg = base.split('Pkg', 1)[1].lower()
            variations.append(after_pkg)
            after_pkg_snake = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', after_pkg)
            after_pkg_snake = re.sub('([a-z0-9])([A-Z])', r'\1_\2', after_pkg_snake).lower()
            variations.append(after_pkg_snake)
        
        # 4. Extract package prefix
        for delim in ['Pkg', 'pkg']:
            if delim in base:
                pkg_part = base.split(delim)[0]
                pkg_snake = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', pkg_part)
                pkg_snake = re.sub('([a-z0-9])([A-Z])', r'\1_\2', pkg_snake).lower()
                variations.append(f"{pkg_snake}_pkg")
                variations.append(pkg_snake)
        
        # NOTE: Don't extract from stored keys - too ambiguous!
        
        # Remove duplicates
        variations = list(dict.fromkeys(v for v in variations if v))
        
        logger.info(f"  Variations tried: {variations[:10]}")
        
        # Try to find match with priority-based approach
        # Collect all potential matches with priority
        all_matches = []
        for var in variations:
            var_lower = var.lower()
            for stored_key in stored_keys:
                stored_key_lower = stored_key.lower()
                
                # Strategy 1: Full stored key match
                if var_lower == stored_key_lower:
                    all_matches.append((stored_key, 100, 0))
                
                # Strategy 2: Stored key contains variation as substring
                # e.g., var="invoice_api_pkg_create_invoice" matches stored_key="invoice_api_pkg.create_invoice"
                elif var_lower.replace('_', '') == stored_key_lower.replace('_', '').replace('.', ''):
                    all_matches.append((stored_key, 95, 0))
                
                # Strategy 3: Match on full stored key with dots/underscores removed
                elif var_lower in stored_key_lower or (var_lower.replace('_', '') in stored_key_lower.replace('_', '').replace('.', '')):
                    # Calculate how well this matches - prefer exact substring matches
                    if '.' in stored_key_lower:
                        pkg_part, proc_part = stored_key_lower.rsplit('.', 1)
                        
                        # Perfect match on procedure part
                        if var_lower == proc_part:
                            all_matches.append((stored_key, 90, len(proc_part)))
                        # Match on package.procedure combination
                        elif var_lower == f"{pkg_part}_{proc_part}" or var_lower == f"{pkg_part}_{proc_part}".replace('_pkg_', '_'):
                            all_matches.append((stored_key, 85, 0))
                        # Partial match
                        elif proc_part in var_lower or var_lower in f"{pkg_part}_{proc_part}":
                            all_matches.append((stored_key, 60, 0))
        
        found_match = None
        if all_matches:
            # Sort by: priority desc, then by match length desc (longer matches are better)
            all_matches.sort(key=lambda x: (-x[1], -x[2], x[0]))
            found_match = all_matches[0][0]
            logger.info(f"  Matches found: {len(all_matches)}, best: {found_match}")
        
        expected = expected_matches.get(service_name)
        if found_match == expected:
            logger.info(f"  ✓ PASS: Found '{found_match}'")
            passed += 1
        else:
            logger.error(f"  ✗ FAIL: Expected '{expected}', got '{found_match}'")
            failed += 1
    
    logger.info("\n" + "=" * 80)
    logger.info(f"Results: {passed} passed, {failed} failed out of {len(test_service_names)} tests")
    
    return failed == 0

if __name__ == '__main__':
    success = test_procedure_name_matching()
    exit(0 if success else 1)
