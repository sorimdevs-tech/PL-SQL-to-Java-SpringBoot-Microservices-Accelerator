"""
LLM Prompt Enhancement - Spring Data Repository Best Practices

This module provides enhancements to LLM prompts to:
1. Generate valid Spring Data repository method calls
2. Provide examples of proper repository signatures
3. Include discovered table metadata in prompts
4. Prevent LLM from inventing non-existent methods
"""

from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class RepositoryEnchancements:
    """Enhancements for repository-related LLM prompts"""
    
    @staticmethod
    def get_spring_data_examples() -> str:
        """Get examples of valid Spring Data method calls"""
        return """
=== VALID SPRING DATA REPOSITORY PATTERNS ===

1. FINDING/QUERYING Records:
   ✓ CORRECT: Optional<User> user = userRepository.findById(userId);
   ✓ CORRECT: User user = userRepository.findById(userId).orElseThrow();
   ✓ CORRECT: List<User> users = userRepository.findAll();
   ✗ WRONG: User user = userRepository.findOne(userId);  // findOne doesn't exist in Spring Data! 
   ✗ WRONG: User user = userRepository.find(bookid LIKE auxItemID);  // Invalid syntax!

2. INSERTING Records (Use JPA save() method):
   ✓ CORRECT: User newUser = new User(); newUser.setName("John"); userRepository.save(newUser);
   ✓ CORRECT: User u = new User(); u.setEmail("test@test.com"); userRepository.saveAndFlush(u);
   ✗ WRONG: userRepository.insertUser(name, email);  // No such method unless custom @Query defined

3. UPDATING Records (find → modify → save):
   ✓ CORRECT: 
     User user = userRepository.findById(id).orElseThrow();
     user.setStatus("ACTIVE");
     userRepository.save(user);
   ✗ WRONG: userRepository.update(user);  // No such method!
   ✗ WRONG: userRepository.setStatus(id, "ACTIVE");  // Wrong pattern!

4. DELETING Records:
   ✓ CORRECT: userRepository.deleteById(userId);
   ✓ CORRECT: userRepository.delete(user);
   ✓ CORRECT: userRepository.deleteAll(users);
   ✗ WRONG: userRepository.remove(userId);  // Wrong method name!

5. QUERYING with Conditions (@Query custom methods):
   ✓ CORRECT (if @Query defined):
     @Query("SELECT u FROM User u WHERE u.email = ?1")
     Optional<User> findByEmail(String email);
   ✓ CORRECT (Spring Data derived queries):
     Optional<User> findByEmail(String email);
     List<User> findByStatus(String status);
   ✗ WRONG: userRepository.findByEmail("test@test.com LIKE '%'");  // Wrong context!

=== RULES FOR REPOSITORY METHOD CALLS ===

A. If a method doesn't exist on the repository, DO NOT call it!
   - Don't invent method names like insertUser, updateUser, getUser
   - Valid JPA methods: save(), findById(), deleteById(), findAll()
   - Only use custom methods if they were explicitly provided

B. When accepting entity objects from parameters:
   - Map SQL parameters to entity fields using setters
   - Example: 
     Order order = new Order();
     order.setCustomerId(pCustomerId);  // ✓ CORRECT if CustomerId field exists
     order.setAmount(pAmount);
     orderRepository.save(order);

C. CRITICAL: Before calling a setter/getter on an entity, verify:
   1. The field exists in the Entity class definition
   2. The Java field name matches what you're calling
   3. The type matches (e.g., setAmount expects BigDecimal, not String)

D. When reading from database results:
   ✓ CORRECT: if (order != null) { BigDecimal amount = order.getAmount(); }
   ✗ WRONG: String amount = order.getAmount();  // Type mismatch!

=== MAPPING SQL OPERATIONS ===

PL/SQL INSERT → Java:
  1. Create new entity: OrderEntity order = new OrderEntity();
  2. Set fields from parameters: order.setCustomerId(pId);
  3. Save: orderRepository.save(order);
  
PL/SQL UPDATE → Java:
  1. Find existing: OrderEntity o = orderRepository.findById(pId).orElseThrow();
  2. Modify fields: o.setStatus("UPDATED");
  3. Save: orderRepository.save(o);  // JPA auto-commits the update

PL/SQL DELETE → Java:
  1. Delete by ID: orderRepository.deleteById(pId);
  2. OR find and delete: OrderEntity o = orderRepository.findById(pId).orElseThrow();
                         orderRepository.delete(o);

PL/SQL SELECT → Java:
  1. Simple: OrderEntity o = orderRepository.findById(pId).orElseThrow();
  2. With condition (if custom @Query exists): Optional<OrderEntity> o = orderRepository.findByStatus("PENDING");
"""
    
    @staticmethod
    def get_entity_usage_rules(entity_fields: str) -> str:
        """Get entity-specific usage rules"""
        return f"""
=== ENTITY FIELD USAGE RULES ===

Available Entity Fields:
{entity_fields}

STRICT RULES:
1. ONLY access fields that are listed above
2. For each field, use EXACTLY the getter/setter names shown:
   - Field "bookid" (String) → getBookid() and setBookid(String)
   - Field "debycost" (BigDecimal) → getDebycost() and setDebycost(BigDecimal)
3. NEVER call getters/setters for fields NOT listed
4. Type MUST match exactly:
   - If field is BigDecimal, pass BigDecimal to setter
   - If field is String, pass String
   - Do NOT convert types arbitrarily

EXAMPLE VIOLATIONS:
✗ row.getVideoid()  — if Videoid is not listed as a field!
✗ row.getCardid()   — if Cardid is not listed as a field!
✗ row.getItemid()   — if Itemid is not listed as a field!

When a field is NOT available:
- Check if you're using the wrong entity (is it supposed to be from VideoEntity instead?)
- Check if the field name is misspelled
- If genuinely missing, create a comment explaining why the field is not available
"""
    
    @staticmethod
    def get_repository_signature_examples(repo_examples: str) -> str:
        """Get repository method signature examples"""
        return f"""
=== REPOSITORY METHOD EXAMPLES ===

These methods are DEFINED and VALID for use:
{repo_examples}

When calling repository methods:
1. USE ONLY the methods shown above
2. Match parameter order EXACTLY
3. Match parameter types EXACTLY
4. If a custom method like insertUser() is shown, it's VALID to call it
5. If a method is NOT shown, DO NOT invent it
"""


class ServiceMethodEnhancement:
    """Enhancements for service method generation"""
    
    @staticmethod
    def get_error_handling_pattern() -> str:
        """Get proper error handling patterns for services"""
        return """
=== ERROR HANDLING IN SERVICES ===

Proper exception handling:

✓ CORRECT:
try {
    OrderEntity order = orderRepository.findById(orderId)
        .orElseThrow(() -> new BusinessException("Order not found"));
    order.setStatus("PROCESSED");
    orderRepository.save(order);
} catch (Exception ex) {
    logger.error("Failed to process order", ex);
    throw new BusinessException("Order processing failed: " + ex.getMessage());
}

✓ Alternative:
Optional<OrderEntity> opt = orderRepository.findById(orderId);
if (opt.isPresent()) {
    OrderEntity order = opt.get();
    // Process order
    orderRepository.save(order);
} else {
    throw new BusinessException("Order not found");
}

✗ WRONG - Don't use raw null checks without explanation:
OrderEntity order = orderRepository.findById(orderId).orElse(null);
if (order == null) {
    // Should throw exception, not silently continue
}
"""
    
    @staticmethod
    def get_transaction_guidelines() -> str:
        """Get transaction handling guidelines"""
        return """
=== TRANSACTION HANDLING ===

Service methods automatically use transactions:
✓ @Service class methods are @Transactional by default in Spring Boot
✓ JPA automatically commits changes to entities that were loaded in transaction
✓ After calling repository.save(), changes are committed when transaction ends

DO NOT manually use @Transactional on service method declarations unless needed.

When a DML operation might fail:
1. Catch specific exceptions (DataIntegrityViolationException, etc.)
2. Rethrow as BusinessException with descriptive message
3. Let @Transactional handle rollback automatically
"""


def enhance_service_prompt_with_metadata(base_prompt: str, 
                                         entity_fields: str,
                                         repo_examples: str) -> str:
    """
    Enhance a service generation prompt with repository guidance
    
    Args:
        base_prompt: Original service template prompt
        entity_fields: Available entity fields formatted for display
        repo_examples: Repository method examples
    
    Returns:
        Enhanced prompt with additional guidelines
    """
    examples = RepositoryEnchancements.get_spring_data_examples()
    entity_rules = RepositoryEnchancements.get_entity_usage_rules(entity_fields)
    repo_sigs = RepositoryEnchancements.get_repository_signature_examples(repo_examples)
    error_handling = ServiceMethodEnhancement.get_error_handling_pattern()
    transactions = ServiceMethodEnhancement.get_transaction_guidelines()
    
    # Insert after the basic requirements section
    insertion_point = base_prompt.find("STRICT OUTPUT RULES")
    if insertion_point == -1:
        insertion_point = len(base_prompt) - 200  # Near the end
    
    enhancements = f"""
{examples}

{entity_rules}

{repo_sigs}

{error_handling}

{transactions}
"""
    
    return base_prompt[:insertion_point] + enhancements + "\n" + base_prompt[insertion_point:]


def create_service_call_validator() -> str:
    """Get a validation checklist for generated service code"""
    return """
=== VALIDATION CHECKLIST FOR GENERATED SERVICE CODE ===

Before emitting a service method, verify:

[] 1. All repository method calls use ONLY methods that exist
[] 2. All parameter types match the method signature exactly
[] 3. All entity field accesses (get/set) correspond to actual fields
[] 4. No invented methods like insertXxx, updateXxx, findOne, etc.
[] 5. Query syntax is valid (if using @Query, syntax is correct)
[] 6. Type conversions are handled (e.g., Long → BigDecimal where needed)
[] 7. Exception handling is present for repository.findById().orElseThrow()
[] 8. Transaction boundaries are correct (no nested @Transactional needed)
[] 9. All imports reference existing classes in the project
[] 10. Method returns void (controller handles response format)
"""
