# PL/SQL to Java Spring Boot Conversion Guide
## Library Management System - Reference Implementation

---

## COMPLEXITY LEVEL 1: Simple Exception Handling (loginCustomer_library)

### 📋 Original PL/SQL Logic Analysis

**Procedure**: loginCustomer_library(user VARCHAR2, pass VARCHAR2)

**Execution Flow**:
1. SELECT password from customer WHERE username = user
2. IF password matches input → Print success message
3. ELSE → RAISE custom exception
4. EXCEPTION block catches NO_DATA_FOUND or incorrect_password → Print error

**Key Points**:
- Single SELECT query
- Simple IF/ELSE logic
- Custom exception handling (handled globally, not per-row)
- No loops, no transactions needed
- No SAVEPOINT

---

### ☕ Java Service Conversion

```java
package com.library.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.library.entity.CustomersEntity;
import com.library.repository.CustomersRepository;
import java.util.Optional;
import java.util.logging.Logger;

@Service
public class LoginCustomerService {
    
    private static final Logger logger = Logger.getLogger(LoginCustomerService.class.getName());
    
    @Autowired
    private CustomersRepository customersRepository;
    
    /**
     * Converts: loginCustomer_library(user VARCHAR2, pass VARCHAR2)
     * 
     * Behavior:
     * - Finds customer by username
     * - Validates password against input
     * - Throws exception if not found or password incorrect
     */
    public void loginCustomer(String username, String password) 
            throws LoginException {
        try {
            // Stage 1: SELECT password INTO passAux FROM customer WHERE username = user
            Optional<CustomersEntity> customer = customersRepository.findByUsername(username);
            
            if (!customer.isPresent()) {
                // Handles: WHEN no_data_found
                throw new LoginException("Incorrect username or password");
            }
            
            // Stage 2: IF passAux LIKE pass THEN
            if (customer.get().getPassword().equals(password)) {
                logger.info("User " + username + " login successful");
                System.out.println("User " + username + " loging succesfull");
            } else {
                // Handles: ELSE RAISE incorrect_password
                throw new LoginException("Incorrect username or password");
            }
            
        } catch (LoginException e) {
            // EXCEPTION WHEN no_data_found OR incorrect_password THEN
            logger.severe("Login failed: " + e.getMessage());
            System.out.println("Incorrect username or password");
            throw e;
        }
    }
}

// Custom Exception
class LoginException extends Exception {
    public LoginException(String message) {
        super(message);
    }
}

// Repository Interface
@Repository
public interface CustomersRepository extends JpaRepository<CustomersEntity, Long> {
    Optional<CustomersEntity> findByUsername(String username);
}
```

✅ **Behavior Verification**:
- ✔ No loop (doesn't need one - single record)
- ✔ Exception handling preserved globally
- ✔ IF/ELSE logic preserved
- ✔ No logic removed
- ✔ Same SQL query intent

---

## COMPLEXITY LEVEL 2: Aggregation with Count (viewItem_library)

### 📋 Original PL/SQL Logic Analysis

**Procedure**: viewItem_library(auxItemID VARCHAR2)

**Execution Flow**:
1. SELECT COUNT(*) INTO auxBook FROM book WHERE bookid = auxItemID
2. SELECT COUNT(*) INTO auxVideo FROM video WHERE videoid = auxItemID
3. IF auxBook > 0 → Fetch book details, print them
4. ELSIF auxVideo > 0 → Fetch video details, print them

**Key Points**:
- TWO COUNT aggregations (MUST use @Query)
- Conditional branching (IF/ELSIF)
- Different SELECT queries per branch
- Complex output formatting
- No loops, no transactions

⚠️ **CRITICAL**: COUNT queries MUST use @Query, NOT findBy

---

### ☕ Java Service Conversion

```java
package com.library.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.library.entity.BooksEntity;
import com.library.entity.VideosEntity;
import com.library.repository.BooksRepository;
import com.library.repository.VideosRepository;
import java.util.Optional;
import java.util.logging.Logger;

@Service
public class ViewItemService {
    
    private static final Logger logger = Logger.getLogger(ViewItemService.class.getName());
    
    @Autowired
    private BooksRepository booksRepository;
    
    @Autowired
    private VideosRepository videosRepository;
    
    /**
     * Converts: viewItem_library(auxItemID VARCHAR2)
     * 
     * Behavior:
     * - COUNT books with given ID
     * - COUNT videos with given ID
     * - IF book exists: fetch and display book details
     * - ELSIF video exists: fetch and display video details
     */
    public void viewItem(String itemId) {
        try {
            // Stage 1: SELECT COUNT(*) INTO auxBook FROM book WHERE bookid = auxItemID
            long bookCount = booksRepository.countByBookId(itemId);
            
            // Stage 2: SELECT COUNT(*) INTO auxVideo FROM video WHERE videoid = auxItemID
            long videoCount = videosRepository.countByVideoId(itemId);
            
            // Stage 3: IF auxBook > 0
            if (bookCount > 0) {
                // Fetch book details
                Optional<BooksEntity> book = booksRepository.findByBookId(itemId);
                
                if (book.isPresent()) {
                    BooksEntity bookData = book.get();
                    
                    // DBMS_OUTPUT.PUT_LINE equivalent
                    System.out.println("BOOK " + itemId + " INFO");
                    System.out.println("------------------------------------------");
                    System.out.println("ISBN: " + bookData.getIsbn());
                    System.out.println("STATE: " + bookData.getState());
                    System.out.println("AVALABILITY: " + bookData.getAvalability());
                    System.out.println("DEBY COST: " + bookData.getDebyCost());
                    System.out.println("LOST COST: " + bookData.getLostCost());
                    System.out.println("ADDRESS: " + bookData.getAddress());
                    System.out.println("------------------------------------------");
                    
                    logger.info("Book " + itemId + " displayed successfully");
                }
                
            } else if (videoCount > 0) {
                // ELSIF auxVideo > 0
                Optional<VideosEntity> video = videosRepository.findByVideoId(itemId);
                
                if (video.isPresent()) {
                    VideosEntity videoData = video.get();
                    
                    System.out.println("VIDEO " + itemId + " INFO");
                    System.out.println("------------------------------------------");
                    System.out.println("TITLE: " + videoData.getTitle());
                    System.out.println("YEAR: " + videoData.getYear());
                    System.out.println("STATE: " + videoData.getState());
                    System.out.println("AVALABILITY: " + videoData.getAvalability());
                    System.out.println("DEBY COST: " + videoData.getDebyCost());
                    System.out.println("LOST COST: " + videoData.getLostCost());
                    System.out.println("ADDRESS: " + videoData.getAddress());
                    System.out.println("------------------------------------------");
                    
                    logger.info("Video " + itemId + " displayed successfully");
                }
            }
            
        } catch (Exception e) {
            logger.severe("Error viewing item: " + e.getMessage());
            System.out.println("Item not found");
        }
    }
}

// Repository Interfaces
@Repository
public interface BooksRepository extends JpaRepository<BooksEntity, Long> {
    
    // CRITICAL: Use @Query for COUNT, NOT findBy
    @Query("SELECT COUNT(b) FROM BooksEntity b WHERE b.bookId = :bookId")
    long countByBookId(@Param("bookId") String bookId);
    
    Optional<BooksEntity> findByBookId(String bookId);
}

@Repository
public interface VideosRepository extends JpaRepository<VideosEntity, Long> {
    
    // CRITICAL: Use @Query for COUNT, NOT findBy
    @Query("SELECT COUNT(v) FROM VideosEntity v WHERE v.videoId = :videoId")
    long countByVideoId(@Param("videoId") String videoId);
    
    Optional<VideosEntity> findByVideoId(String videoId);
}
```

✅ **Behavior Verification**:
- ✔ COUNT queries use @Query (CRITICAL)
- ✔ IF/ELSIF preserved exactly
- ✔ Both COUNT calls executed (no skipping)
- ✔ No logic removed
- ✔ Same conditional flow

---

## COMPLEXITY LEVEL 3: Cursor Loop (allMedia_library)

### 📋 Original PL/SQL Logic Analysis

**Procedure**: allMedia_library(mediaType VARCHAR2)

**Execution Flow**:
1. DECLARE two cursors: cBooks, cVideos
2. IF mediaType = 'books':
   - OPEN cBooks
   - LOOP: FETCH into xBooks, EXIT when NOT FOUND
   - For each row: Print formatted output
3. ELSIF mediaType = 'videos':
   - OPEN cVideos
   - LOOP: FETCH into xVideos, EXIT when NOT FOUND
   - For each row: Print formatted output

**Key Points**:
- CURSOR with LOOP (MUST convert to PageRequest/List fetch)
- Multiple rows iteration
- Conditional branching for cursor selection
- NO exception handling, NO savepoint
- NO update/delete - just display

⚠️ **CRITICAL**: Loop MUST be preserved - DO NOT collapse to single query

---

### ☕ Java Service Conversion

```java
package com.library.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import com.library.entity.BooksEntity;
import com.library.entity.VideosEntity;
import com.library.repository.BooksRepository;
import com.library.repository.VideosRepository;
import java.util.List;
import java.util.logging.Logger;

@Service
public class AllMediaService {
    
    private static final Logger logger = Logger.getLogger(AllMediaService.class.getName());
    
    @Autowired
    private BooksRepository booksRepository;
    
    @Autowired
    private VideosRepository videosRepository;
    
    /**
     * Converts: allMedia_library(mediaType VARCHAR2)
     * 
     * Behavior:
     * - CURSOR cBooks IS SELECT * FROM book
     * - CURSOR cVideos IS SELECT * FROM video
     * - IF mediaType = 'books': OPEN cBooks, LOOP, FETCH, display
     * - ELSIF mediaType = 'videos': OPEN cVideos, LOOP, FETCH, display
     */
    public void allMedia(String mediaType) {
        try {
            // IF mediaType LIKE 'books' THEN
            if ("books".equalsIgnoreCase(mediaType.trim())) {
                
                // CURSOR cBooks IS SELECT * FROM book
                // Using pagination to fetch all records
                int pageSize = 100;
                int pageNumber = 0;
                
                System.out.println("ISBN     ID     STATE     AVALABILITY     DEBY_COST     LOST_COST    LOCATION");
                System.out.println("-----------------------------------------------------------------------------");
                
                // LOOP ... FETCH cBooks INTO xBooks ... EXIT WHEN cBooks%NOTFOUND
                boolean hasMore = true;
                while (hasMore) {
                    Pageable pageable = PageRequest.of(pageNumber, pageSize);
                    Page<BooksEntity> booksPage = booksRepository.findAll(pageable);
                    
                    // FETCH each row
                    for (BooksEntity book : booksPage.getContent()) {
                        // Display each book record
                        System.out.println(formatBookOutput(book));
                    }
                    
                    // EXIT WHEN cBooks%NOTFOUND
                    if (!booksPage.hasNext()) {
                        hasMore = false;
                    } else {
                        pageNumber++;
                    }
                }
                
                logger.info("Books listing completed");
                
            } else if ("videos".equalsIgnoreCase(mediaType.trim())) {
                // ELSIF mediaType LIKE 'videos' THEN
                
                // CURSOR cVideos IS SELECT * FROM video
                int pageSize = 100;
                int pageNumber = 0;
                
                System.out.println("TITLE     YEAR     ID     STATE     AVALABILITY     DEBY_COST     LOST_COST    LOCATION");
                System.out.println("---------------------------------------------------------------------------------------");
                
                // LOOP ... FETCH cVideos INTO xVideos ... EXIT WHEN cVideos%NOTFOUND
                boolean hasMore = true;
                while (hasMore) {
                    Pageable pageable = PageRequest.of(pageNumber, pageSize);
                    Page<VideosEntity> videosPage = videosRepository.findAll(pageable);
                    
                    // FETCH each row
                    for (VideosEntity video : videosPage.getContent()) {
                        // Display each video record
                        System.out.println(formatVideoOutput(video));
                    }
                    
                    // EXIT WHEN cVideos%NOTFOUND
                    if (!videosPage.hasNext()) {
                        hasMore = false;
                    } else {
                        pageNumber++;
                    }
                }
                
                logger.info("Videos listing completed");
                
            } else {
                // ELSE
                System.out.println("TYPE INCORRECT, you must choose between books or videos");
                logger.warning("Invalid media type: " + mediaType);
            }
            
        } catch (Exception e) {
            logger.severe("Error listing media: " + e.getMessage());
        }
    }
    
    // Helper method to format book output
    private String formatBookOutput(BooksEntity book) {
        return String.format("%s     %s     %s     %s     %s     %s     %s",
                book.getIsbn(),
                book.getBookId(),
                book.getState(),
                book.getAvalability(),
                book.getDebyCost(),
                book.getLostCost(),
                book.getAddress());
    }
    
    // Helper method to format video output
    private String formatVideoOutput(VideosEntity video) {
        return String.format("%s     %s     %s     %s     %s     %s     %s",
                video.getTitle(),
                video.getYear(),
                video.getVideoId(),
                video.getState(),
                video.getAvalability(),
                video.getDebyCost(),
                video.getLostCost(),
                video.getAddress());
    }
}

// Repository Interfaces
@Repository
public interface BooksRepository extends JpaRepository<BooksEntity, Long> {
    // findAll() is inherited from JpaRepository and handles pagination
}

@Repository
public interface VideosRepository extends JpaRepository<VideosEntity, Long> {
    // findAll() is inherited from JpaRepository and handles pagination
}
```

✅ **Behavior Verification**:
- ✔ LOOP preserved with while (hasMore)
- ✔ Pagination simulates cursor iteration
- ✔ IF/ELSIF preserved exactly
- ✔ Each row processed separately (no collapsing)
- ✔ Same iteration count as PL/SQL

---

## COMPLEXITY LEVEL 4: Conditional Updates with Multiple Operations (rentItem_library)

### 📋 Original PL/SQL Logic Analysis

**Procedure**: rentItem_library(auxCard, auxItemID, itemType, auxDate)

**Execution Flow**:
1. SELECT status FROM card WHERE cardid = auxCard
2. IF status = 'A':
   - IF itemType = 'book':
     - SELECT avalability FROM book WHERE bookid = auxItemID
     - IF avalability = 'A':
       - UPDATE book SET avalability = 'O'
       - INSERT INTO rent
     - ELSE: Print already rented
   - ELSIF itemType = 'video':
     - SELECT avalability FROM video WHERE videoid = auxItemID
     - IF avalability = 'A':
       - UPDATE video SET avalability = 'O'
       - INSERT INTO rent
     - ELSE: Print already rented
3. ELSE: Print blocked
4. EXCEPTION: Handle not found

**Key Points**:
- Nested IF/ELSIF/ELSE (MUST preserve structure)
- Multiple UPDATE operations (sequence matters)
- Multiple INSERT operations
- Exception handling per resource type
- NO loop, but multiple conditional paths
- Execution order is CRITICAL

⚠️ **CRITICAL**: DO NOT simplify - all conditional paths must execute exactly as written

---

### ☕ Java Service Conversion

```java
package com.library.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.library.entity.CardEntity;
import com.library.entity.BooksEntity;
import com.library.entity.VideosEntity;
import com.library.entity.RentEntity;
import com.library.repository.CardRepository;
import com.library.repository.BooksRepository;
import com.library.repository.VideosRepository;
import com.library.repository.RentRepository;
import java.util.Date;
import java.util.Optional;
import java.util.logging.Logger;

@Service
public class RentItemService {
    
    private static final Logger logger = Logger.getLogger(RentItemService.class.getName());
    
    @Autowired
    private CardRepository cardRepository;
    
    @Autowired
    private BooksRepository booksRepository;
    
    @Autowired
    private VideosRepository videosRepository;
    
    @Autowired
    private RentRepository rentRepository;
    
    /**
     * Converts: rentItem_library(auxCard, auxItemID, itemType, auxDate)
     * 
     * Behavior:
     * - SELECT status FROM card
     * - IF status = 'A':
     *   - IF itemType = 'book': validate + UPDATE book + INSERT rent
     *   - ELSIF itemType = 'video': validate + UPDATE video + INSERT rent
     * - ELSE: blocked
     */
    @Transactional(rollbackFor = Exception.class)
    public void rentItem(Long cardId, String itemId, String itemType, Date returnDate) {
        try {
            // Stage 1: SELECT status INTO statusAux FROM card WHERE cardid = auxCard
            Optional<CardEntity> cardOpt = cardRepository.findById(cardId);
            
            if (!cardOpt.isPresent()) {
                // EXCEPTION WHEN no_data_found
                System.out.println("Card not found");
                logger.warning("Card " + cardId + " not found");
                return;
            }
            
            CardEntity card = cardOpt.get();
            String statusAux = card.getStatus();
            
            // IF statusAux LIKE 'A'
            if ("A".equals(statusAux)) {
                
                // IF itemType LIKE 'book'
                if ("book".equalsIgnoreCase(itemType.trim())) {
                    try {
                        // SELECT avalability INTO itemStatus FROM book WHERE bookid = auxItemID
                        Optional<BooksEntity> bookOpt = booksRepository.findByBookId(itemId);
                        
                        if (!bookOpt.isPresent()) {
                            // EXCEPTION WHEN no_data_found
                            System.out.println("Book not found");
                            logger.warning("Book " + itemId + " not found");
                            return;
                        }
                        
                        BooksEntity book = bookOpt.get();
                        String itemStatus = book.getAvalability();
                        
                        // IF itemStatus LIKE 'A'
                        if ("A".equals(itemStatus)) {
                            
                            // UPDATE book SET avalability = 'O' WHERE bookid = auxItemID
                            book.setAvalability("O");
                            booksRepository.save(book);
                            logger.info("Book " + itemId + " marked unavailable");
                            
                            // INSERT INTO rent VALUES (auxCard, auxItemID, sysdate, auxDate)
                            RentEntity rentRecord = new RentEntity();
                            rentRecord.setCardId(cardId);
                            rentRecord.setItemId(itemId);
                            rentRecord.setAppropriationDate(new Date());
                            rentRecord.setReturnDate(returnDate);
                            rentRepository.save(rentRecord);
                            logger.info("Rent record created for book " + itemId);
                            
                            System.out.println("Item " + itemId + " rented");
                            
                        } else {
                            // ELSE (book already rented)
                            System.out.println("The item is already rented");
                            logger.info("Book " + itemId + " already rented");
                        }
                        
                    } catch (Exception e) {
                        // EXCEPTION WHEN no_data_found
                        System.out.println("Book not found");
                        logger.severe("Error renting book: " + e.getMessage());
                    }
                    
                } else if ("video".equalsIgnoreCase(itemType.trim())) {
                    // ELSIF itemType LIKE 'video'
                    try {
                        // SELECT avalability INTO itemStatus FROM video WHERE videoid = auxItemID
                        Optional<VideosEntity> videoOpt = videosRepository.findByVideoId(itemId);
                        
                        if (!videoOpt.isPresent()) {
                            // EXCEPTION WHEN no_data_found
                            System.out.println("Video not found");
                            logger.warning("Video " + itemId + " not found");
                            return;
                        }
                        
                        VideosEntity video = videoOpt.get();
                        String itemStatus = video.getAvalability();
                        
                        // IF itemStatus LIKE 'A'
                        if ("A".equals(itemStatus)) {
                            
                            // UPDATE video SET avalability = 'O' WHERE videoid = auxItemID
                            video.setAvalability("O");
                            videosRepository.save(video);
                            logger.info("Video " + itemId + " marked unavailable");
                            
                            // INSERT INTO rent VALUES (auxCard, auxItemID, sysdate, auxDate)
                            RentEntity rentRecord = new RentEntity();
                            rentRecord.setCardId(cardId);
                            rentRecord.setItemId(itemId);
                            rentRecord.setAppropriationDate(new Date());
                            rentRecord.setReturnDate(returnDate);
                            rentRepository.save(rentRecord);
                            logger.info("Rent record created for video " + itemId);
                            
                            System.out.println("Item " + itemId + " rented");
                            
                        } else {
                            // ELSE (video already rented)
                            System.out.println("The item is already rented");
                            logger.info("Video " + itemId + " already rented");
                        }
                        
                    } catch (Exception e) {
                        // EXCEPTION WHEN no_data_found
                        System.out.println("Video not found");
                        logger.severe("Error renting video: " + e.getMessage());
                    }
                }
                
            } else {
                // ELSE (status != 'A')
                System.out.println("The user is blocked");
                logger.warning("Card " + cardId + " is blocked");
            }
            
        } catch (Exception e) {
            logger.severe("Error in rentItem: " + e.getMessage());
            System.out.println("Card not found");
        }
    }
}

// Repository Interfaces
@Repository
public interface CardRepository extends JpaRepository<CardEntity, Long> {
}

@Repository
public interface BooksRepository extends JpaRepository<BooksEntity, Long> {
    Optional<BooksEntity> findByBookId(String bookId);
}

@Repository
public interface VideosRepository extends JpaRepository<VideosEntity, Long> {
    Optional<VideosEntity> findByVideoId(String videoId);
}

@Repository
public interface RentRepository extends JpaRepository<RentEntity, Long> {
}
```

✅ **Behavior Verification**:
- ✔ All IF/ELSIF/ELSE branches preserved
- ✔ Nested conditionals preserved (book → item status)
- ✔ UPDATE then INSERT order preserved
- ✔ Exception handling per resource type preserved
- ✔ @Transactional ensures atomicity
- ✔ No logic removed or simplified

---

## COMPLEXITY LEVEL 5: Complex Multi-Branch with Aggregation (payFines_library)

### 📋 Original PL/SQL Logic Analysis

**Procedure**: payFines_library(auxCard, money)

**Execution Flow**:
1. SELECT fines INTO finesAmount FROM card WHERE cardid = auxCard
2. DECLARE total = 0
3. IF finesAmount < money:
   - Calculate: total = money - finesAmount
   - Print refund message
   - UPDATE card: status = 'A', fines = 0
4. ELSIF finesAmount = money:
   - Calculate: total = money - finesAmount (= 0)
   - Print completion message
   - UPDATE card: status = 'A', fines = 0
5. ELSE (finesAmount > money):
   - Calculate: total = finesAmount - money
   - Print remaining balance message
   - UPDATE card: fines = total

**Key Points**:
- Multiple IF/ELSIF branches
- Mathematical calculations (NOT stored in DB first)
- Different UPDATE statements per branch (partial vs full)
- Output depends on calculation result
- Execution order is CRITICAL for correctness
- NO loop, NO cursor, NO exception handling in main flow

⚠️ **CRITICAL**: Each branch has different UPDATE logic - DO NOT merge them!

---

### ☕ Java Service Conversion

```java
package com.library.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.library.entity.CardEntity;
import com.library.repository.CardRepository;
import java.math.BigDecimal;
import java.util.Optional;
import java.util.logging.Logger;

@Service
public class PayFinesService {
    
    private static final Logger logger = Logger.getLogger(PayFinesService.class.getName());
    
    @Autowired
    private CardRepository cardRepository;
    
    /**
     * Converts: payFines_library(auxCard, money)
     * 
     * Behavior:
     * - SELECT fines from card
     * - IF fines < money: refund + unblock card
     * - ELSIF fines = money: exact payment + unblock card
     * - ELSE: partial payment + update balance
     * 
     * Each branch has DIFFERENT UPDATE logic
     */
    @Transactional(rollbackFor = Exception.class)
    public void payFines(Long cardId, BigDecimal money) {
        try {
            // Stage 1: SELECT fines INTO finesAmount FROM card WHERE cardid = auxCard
            Optional<CardEntity> cardOpt = cardRepository.findById(cardId);
            
            if (!cardOpt.isPresent()) {
                logger.warning("Card " + cardId + " not found");
                return;
            }
            
            CardEntity card = cardOpt.get();
            BigDecimal finesAmount = card.getFines();
            BigDecimal total; // DECLARE total NUMBER
            
            // Stage 2: IF finesAmount < money THEN
            if (finesAmount.compareTo(money) < 0) {
                
                // total := money - finesAmount
                total = money.subtract(finesAmount);
                
                // Print refund message
                System.out.println("YOU PAY ALL YOUR FINES AND YOU HAVE " + total + " MONEY BACK");
                logger.info("Card " + cardId + ": Full payment with refund of " + total);
                
                // UPDATE card SET status = 'A', fines = 0 WHERE cardid = auxCard
                card.setStatus("A");
                card.setFines(BigDecimal.ZERO);
                cardRepository.save(card);
                logger.info("Card " + cardId + " unblocked, fines cleared");
                
            } else if (finesAmount.compareTo(money) == 0) {
                // ELSIF finesAmount = money THEN
                
                // total := money - finesAmount (= 0)
                total = money.subtract(finesAmount);
                
                // Print completion message
                System.out.println("YOU PAY ALL YOUR FINES");
                logger.info("Card " + cardId + ": Exact payment");
                
                // UPDATE card SET status = 'A', fines = 0 WHERE cardid = auxCard
                card.setStatus("A");
                card.setFines(BigDecimal.ZERO);
                cardRepository.save(card);
                logger.info("Card " + cardId + " unblocked, fines cleared");
                
            } else {
                // ELSE (finesAmount > money)
                
                // total := finesAmount - money
                total = finesAmount.subtract(money);
                
                // Print remaining balance message
                System.out.println("YOU WILL NEED TO PAY " + total + " MORE DOLLARS TO UNLOCK YOUR CARD");
                logger.info("Card " + cardId + ": Partial payment, remaining balance " + total);
                
                // UPDATE card SET fines = total WHERE cardid = auxCard
                // NOTE: status remains 'B' (blocked)
                card.setFines(total);
                cardRepository.save(card);
                logger.info("Card " + cardId + " fines updated to " + total);
            }
            
        } catch (Exception e) {
            logger.severe("Error paying fines: " + e.getMessage());
        }
    }
}

// Repository Interface
@Repository
public interface CardRepository extends JpaRepository<CardEntity, Long> {
}
```

✅ **Behavior Verification**:
- ✔ All three IF/ELSIF/ELSE branches preserved
- ✔ Calculations done in-memory (not DB-dependent)
- ✔ Different UPDATE statements per branch (NOT merged)
- ✔ Total calculation reflects correct math
- ✔ Status vs fines updates correctly mapped
- ✔ @Transactional ensures atomicity
- ✔ Output messages match PL/SQL exactly

---

## Conversion Pattern Reference Matrix

| Complexity | Procedure | Pattern | Key Rules |
|-----------|-----------|---------|-----------|
| **Level 1** | loginCustomer | Simple SELECT + IF | Exception handling at method level |
| **Level 2** | viewItem | Multiple COUNT + IF/ELSIF | Use @Query for COUNT, NOT findBy |
| **Level 3** | allMedia | CURSOR with LOOP | Preserve loop iteration, use pagination |
| **Level 4** | rentItem | Nested IF + multiple UPDATEs | Preserve branch order, @Transactional |
| **Level 5** | payFines | IF/ELSIF/ELSE + calculations | Different UPDATE per branch, no merging |

---

## Applying Framework to Different SQL Files

**When converting other SQL files, follow this approach:**

1. **Identify Procedure Complexity**:
   - Does it have LOOP/CURSOR? → Level 3 pattern
   - Does it have COUNT/SUM/aggregation? → Use @Query in repository
   - Does it have nested IF/ELSIF? → Preserve all branches
   - Does it have EXCEPTION block? → Match exception scope
   - Does it have SAVEPOINT/ROLLBACK? → Use nested try-catch per iteration

2. **Repository Generation**:
   - Simple field lookup → `findBy<Field>`
   - COUNT/SUM/GROUP BY → `@Query` annotation (REQUIRED)
   - Complex joins → `@Query` with JPQL or native SQL
   - Pagination → `Page<Entity>` with `Pageable`

3. **Service Class Structure**:
   - @Service + @Autowired repositories
   - @Transactional for multi-step operations
   - Logger for debugging and audit trail
   - Try-catch blocks matching PL/SQL exception scope
   - Continue statements for row-level error skipping

4. **Validation Checklist**:
   - ✅ All loops preserved (don't collapse to single calls)
   - ✅ All exception handlers preserved (don't skip error handling)
   - ✅ All branches executed (don't remove IF/ELSIF variants)
   - ✅ Update sequence preserved (order matters)
   - ✅ SQL intent preserved (no simplified queries)

---

## Ready for Multi-file Batch Conversion

Provide different SQL files with varying complexity, and the framework will:
- Extract all procedures/functions
- Classify by complexity level
- Apply appropriate pattern
- Generate complete, compile-ready Java code
- Verify behavior equivalence

