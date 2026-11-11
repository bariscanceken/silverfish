package com.silverfish.mclibrary;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParseException;
import com.google.gson.JsonParser;

/**
 * Talks to the Python service. Every call is asynchronous: requests and JSON parsing run on
 * the HTTP client's threads, never on the server thread. Callers must hop back to the server
 * thread (for example with {@code server.execute}) before touching the world.
 */
public final class LibraryServiceClient {
	public record Book(String id, String title, String author, List<String> pages, String source) {
	}

	public record Skipped(String file, String reason) {
	}

	public record Plan(List<Book> books, List<Skipped> skipped) {
	}

	/** The service answered, but with an error status. */
	public static final class ServiceException extends RuntimeException {
		public ServiceException(String message) {
			super(message);
		}
	}

	private final HttpClient http;
	private final URI baseUrl;
	private final Duration timeout;

	public LibraryServiceClient(ModConfig config) {
		this.baseUrl = config.serviceUrl();
		this.timeout = Duration.ofSeconds(config.timeoutSeconds());
		this.http = HttpClient.newBuilder()
				.connectTimeout(Duration.ofSeconds(5))
				.build();
	}

	public URI baseUrl() {
		return baseUrl;
	}

	public Duration timeout() {
		return timeout;
	}

	public CompletableFuture<Plan> fetchPlan() {
		return post("/plan", "{}").thenApply(LibraryServiceClient::parsePlan);
	}

	/** Reports ids that were put into the chest. Completes with the number of newly recorded ids. */
	public CompletableFuture<Integer> confirm(List<String> ids) {
		JsonArray array = new JsonArray();
		ids.forEach(array::add);
		JsonObject body = new JsonObject();
		body.add("ids", array);
		return post("/onay", body.toString())
				.thenApply(json -> JsonParser.parseString(json).getAsJsonObject().get("accepted").getAsInt());
	}

	private CompletableFuture<String> post(String path, String jsonBody) {
		HttpRequest request = HttpRequest.newBuilder(baseUrl.resolve(path))
				.timeout(timeout)
				.header("Content-Type", "application/json")
				.POST(HttpRequest.BodyPublishers.ofString(jsonBody, StandardCharsets.UTF_8))
				.build();
		return http.sendAsync(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8))
				.thenApply(response -> {
					if (response.statusCode() != 200) {
						throw new ServiceException("Servis hata döndürdü (HTTP %d): %s"
								.formatted(response.statusCode(), errorDetail(response.body())));
					}
					return response.body();
				});
	}

	private static String errorDetail(String body) {
		try {
			JsonElement detail = JsonParser.parseString(body).getAsJsonObject().get("detail");
			if (detail != null) {
				return detail.isJsonPrimitive() ? detail.getAsString() : detail.toString();
			}
		} catch (RuntimeException ignored) {
			// not JSON; fall through
		}
		return body.length() > 200 ? body.substring(0, 200) + "…" : body;
	}

	static Plan parsePlan(String body) {
		try {
			JsonObject root = JsonParser.parseString(body).getAsJsonObject();
			List<Book> books = new ArrayList<>();
			for (JsonElement element : root.getAsJsonArray("books")) {
				JsonObject b = element.getAsJsonObject();
				List<String> pages = new ArrayList<>();
				for (JsonElement page : b.getAsJsonArray("pages")) {
					pages.add(page.getAsString());
				}
				books.add(new Book(
						b.get("id").getAsString(),
						b.get("title").getAsString(),
						b.get("author").getAsString(),
						List.copyOf(pages),
						b.get("source").getAsString()));
			}
			List<Skipped> skipped = new ArrayList<>();
			JsonArray skippedArray = root.getAsJsonArray("skipped");
			if (skippedArray != null) {
				for (JsonElement element : skippedArray) {
					JsonObject s = element.getAsJsonObject();
					skipped.add(new Skipped(s.get("file").getAsString(), s.get("reason").getAsString()));
				}
			}
			return new Plan(List.copyOf(books), List.copyOf(skipped));
		} catch (RuntimeException e) {
			// IllegalStateException, NullPointerException, ... for missing or mistyped fields
			throw new JsonParseException("unexpected /plan response: " + e.getMessage(), e);
		}
	}
}
