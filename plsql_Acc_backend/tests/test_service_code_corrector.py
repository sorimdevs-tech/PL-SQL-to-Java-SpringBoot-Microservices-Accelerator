from src.validator.service_code_corrector import ServiceCodeCorrector


def test_correct_service_code_logic_repairs_get_total_value_aggregation_call():
    service_code = """
public class ViewitemLibraryService {
    private final BookRepository bookRepository;

    public ViewitemLibraryService(BookRepository bookRepository) {
        this.bookRepository = bookRepository;
    }

    public void run(String bookid) {
        bookRepository.getTotalValueByBookid(bookid);
    }
}
"""

    repositories = {
        "BookRepository.java": """
public interface BookRepository {
    @Query("SELECT COALESCE(SUM(e.price), 0) FROM BookEntity e WHERE e.bookId = :bookid")
    BigDecimal getTotalPriceByBookid(@Param("bookid") String bookid);
}
"""
    }

    corrected = ServiceCodeCorrector.correct_service_code_logic(
        service_code,
        repositories=repositories,
    )

    assert "bookRepository.getTotalPriceByBookid(bookid);" in corrected
    assert "getTotalValueByBookid" not in corrected
