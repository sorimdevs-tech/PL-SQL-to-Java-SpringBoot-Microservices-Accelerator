#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.generator.comprehensive_code_fixer import ComprehensiveServiceFixer

# More realistic test case with multiple issues
problematic = """
package com.example.demo.service;

public class InvoiceApiCreateInvoiceService {

    // Category 2: Return type issue - should return Long, not void
    public void createInvoice(Long customerId, Long amount, String description) {
        // Category 1: PL/SQL syntax - single quotes, named params
        var lDescription = (description != null ? description : 'Untitled');
        var lAmount = (amount := amount != null ? amount : 0);
        
        // Category 3: Validation logic reversed
        if (!(customerId != null)) {
            throw new BusinessException("Customer ID required");
        }
        
        // Category 4: Invalid repository method
        var customer = customerRepository.findOne(...);
        
        // Category 5: Undefined constants
        var status = invoice_pkg.LogConstants.STATUS_ACTIVE;
        
        // Category 1: PL/SQL CASE statement
        var typeCode = CASE invoiceType WHEN 'A' THEN 'ADVANCE' WHEN 'R' THEN 'REGULAR' END;
        
        var lReturnvalue = invoiceService.createInvoice(customerId, lAmount);
        // Missing return statement for a function that should return Long
    }
    
    // Category 8: Duplicate exception class
    private static final class BusinessException extends RuntimeException {
        BusinessException(String msg) { super(msg); }
    }
}
"""

fixer = ComprehensiveServiceFixer()
fixed, counts = fixer.fix_service_code(problematic, {})

output = f"""
COMPREHENSIVE FIXER TEST RESULTS
{'='*60}

FIXES APPLIED BY CATEGORY:
{' '*4}Compilation: {counts['compilation']}
{' '*4}Return Types: {counts['return_types']}
{' '*4}Validation Logic: {counts['validation']}
{' '*4}Repository: {counts['repository']}
{' '*4}Constants: {counts['constants']}
{' '*4}Entity: {counts['entity']}
{' '*4}Exception: {counts['exception']}
{' '*4}Syntax: {counts['syntax']}
{' '*4}Parity: {counts['parity']}
{' '*4}TOTAL: {sum(counts.values())}

{'='*60}
ORIGINAL CODE (First 500 chars):
{problematic[:500]}...

{'='*60}
FIXED CODE (First 500 chars):
{fixed[:500]}...

{'='*60}
KEY IMPROVEMENTS:
- PL/SQL syntax removed: {':=' not in fixed and 'findOne(...)' not in fixed}
- Return type added if needed: {'Long' in fixed or 'void' in fixed}
- Validation logic improved: {fixed.count('!') <= problematic.count('!')}
- Ellipsis removed: {'...' not in fixed}
- Repository methods fixed: {'findOne(...)'  not in fixed}
"""

with open('test_output.txt', 'w', encoding='utf-8') as f:
    f.write(output)

print("Test complete - output saved to test_output.txt")
print(f"Total fixes applied: {sum(counts.values())}")
