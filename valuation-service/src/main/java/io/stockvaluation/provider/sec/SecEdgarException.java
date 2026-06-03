package io.stockvaluation.provider.sec;

public class SecEdgarException extends RuntimeException {

    private final String category;

    public SecEdgarException(String category, String message) {
        super(message);
        this.category = category;
    }

    public SecEdgarException(String category, String message, Throwable cause) {
        super(message, cause);
        this.category = category;
    }

    public String getCategory() {
        return category;
    }
}
