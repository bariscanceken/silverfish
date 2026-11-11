package com.silverfish.mclibrary;

import java.io.IOException;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

/**
 * Settings read from {@code config/silverfish_mclibrary.json}. The file is created with
 * defaults on first start. Invalid values are logged and replaced by defaults; the game
 * never fails to start because of this file.
 */
public record ModConfig(URI serviceUrl, int timeoutSeconds) {
	public static final String FILE_NAME = SilverfishMod.MOD_ID + ".json";
	public static final String DEFAULT_URL = "http://127.0.0.1:8765";
	/** Large PDFs can take a while to extract, so never wait less than this. */
	public static final int MIN_TIMEOUT_SECONDS = 30;
	public static final int DEFAULT_TIMEOUT_SECONDS = 60;

	private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

	public static ModConfig defaults() {
		return new ModConfig(URI.create(DEFAULT_URL), DEFAULT_TIMEOUT_SECONDS);
	}

	public static ModConfig load(Path configDir) {
		Path file = configDir.resolve(FILE_NAME);
		if (!Files.exists(file)) {
			ModConfig config = defaults();
			config.save(file);
			return config;
		}

		ModConfig defaults = defaults();
		try {
			JsonObject json = JsonParser.parseString(Files.readString(file, StandardCharsets.UTF_8)).getAsJsonObject();
			URI url = parseUrl(json.get("serviceUrl"), defaults.serviceUrl());
			int timeout = parseTimeout(json.get("timeoutSeconds"));
			return new ModConfig(url, timeout);
		} catch (IOException | RuntimeException e) {
			SilverfishMod.LOGGER.error("Could not read {}, using defaults", file, e);
			return defaults;
		}
	}

	private static URI parseUrl(JsonElement element, URI fallback) {
		if (element == null || !element.isJsonPrimitive()) {
			return fallback;
		}
		try {
			String raw = element.getAsString().strip();
			while (raw.endsWith("/")) {
				raw = raw.substring(0, raw.length() - 1);
			}
			URI uri = URI.create(raw);
			if (!"http".equals(uri.getScheme()) && !"https".equals(uri.getScheme()) || uri.getHost() == null) {
				throw new IllegalArgumentException("not an http(s) URL");
			}
			return uri;
		} catch (IllegalArgumentException e) {
			SilverfishMod.LOGGER.error("Invalid serviceUrl {} in config, using {}", element, fallback);
			return fallback;
		}
	}

	private static int parseTimeout(JsonElement element) {
		if (element == null || !element.isJsonPrimitive() || !element.getAsJsonPrimitive().isNumber()) {
			return DEFAULT_TIMEOUT_SECONDS;
		}
		int value = element.getAsInt();
		if (value < MIN_TIMEOUT_SECONDS) {
			SilverfishMod.LOGGER.warn("timeoutSeconds {} is too low, using {}", value, MIN_TIMEOUT_SECONDS);
			return MIN_TIMEOUT_SECONDS;
		}
		return value;
	}

	private void save(Path file) {
		JsonObject json = new JsonObject();
		json.addProperty("serviceUrl", serviceUrl.toString());
		json.addProperty("timeoutSeconds", timeoutSeconds);
		try {
			Files.createDirectories(file.getParent());
			Files.writeString(file, GSON.toJson(json), StandardCharsets.UTF_8);
		} catch (IOException e) {
			SilverfishMod.LOGGER.error("Could not write default config to {}", file, e);
		}
	}
}
