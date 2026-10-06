package com.repodna.api.job;

public enum SourceType {
    GIT("git"),
    ZIP("zip");

    private final String value;

    SourceType(String value) {
        this.value = value;
    }

    /** The value stored in the database and sent in the queue message. */
    public String value() {
        return value;
    }

    public static SourceType fromValue(String value) {
        for (SourceType type : values()) {
            if (type.value.equals(value)) {
                return type;
            }
        }
        throw new IllegalArgumentException("Unknown source_type: " + value);
    }
}