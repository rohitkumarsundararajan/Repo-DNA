package com.repodna.api.result;

public class ResultNotReadyException extends RuntimeException {
    public ResultNotReadyException(String message) {
        super(message);
    }
}