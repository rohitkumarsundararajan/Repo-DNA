package com.repodna.api.job;

import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;

/** Stores SourceType as 'git' / 'zip' (lowercase) to match the jobs table and the queue message. */
@Converter
public class SourceTypeConverter implements AttributeConverter<SourceType, String> {

    @Override
    public String convertToDatabaseColumn(SourceType attribute) {
        return attribute == null ? null : attribute.value();
    }

    @Override
    public SourceType convertToEntityAttribute(String dbData) {
        return dbData == null ? null : SourceType.fromValue(dbData);
    }
}