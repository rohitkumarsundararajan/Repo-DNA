# Build stage: full JDK + Maven, discarded after packaging
FROM maven:3.9-eclipse-temurin-21 AS build

WORKDIR /build

COPY pom.xml .
RUN mvn -B dependency:go-offline

COPY src ./src
RUN mvn -B clean package -DskipTests

# Runtime stage: lean Java 21 JRE only
FROM eclipse-temurin:21-jre

WORKDIR /app

COPY --from=build /build/target/api-*.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]