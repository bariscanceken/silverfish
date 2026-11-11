package com.silverfish.mclibrary;

import java.net.ConnectException;
import java.net.http.HttpTimeoutException;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.Container;

/**
 * Handles one K press: find the chest, ask the service for books without blocking the
 * server thread, then put the books in the chest and confirm what was actually placed.
 */
public final class BookDelivery {
	private static final int MAX_SKIPPED_LINES = 5;

	private final LibraryServiceClient service;
	/** Players with a request in flight. Only touched on the server thread. */
	private final Set<UUID> inFlight = ConcurrentHashMap.newKeySet();

	public BookDelivery(LibraryServiceClient service) {
		this.service = service;
	}

	/** Called on the server thread when a player presses the key. */
	public void request(MinecraftServer server, ServerPlayer player) {
		if (findChest(player).isEmpty()) {
			send(player, "Yakında " + SilverfishMod.ACCEPT_CHEST_NAME + " sandığı yok", ChatFormatting.RED);
			return;
		}

		UUID playerId = player.getUUID();
		if (!inFlight.add(playerId)) {
			send(player, "Önceki istek hâlâ sürüyor, lütfen bekle.", ChatFormatting.YELLOW);
			return;
		}

		send(player, "Kitaplar hazırlanıyor...", ChatFormatting.GRAY);
		service.fetchPlan().whenComplete((plan, error) ->
				// Back to the server thread before touching players, chests or items.
				server.execute(() -> onPlan(server, playerId, plan, error)));
	}

	private void onPlan(MinecraftServer server, UUID playerId, LibraryServiceClient.Plan plan, Throwable error) {
		inFlight.remove(playerId);
		ServerPlayer player = server.getPlayerList().getPlayer(playerId);
		if (player == null) {
			SilverfishMod.LOGGER.info("Player {} left before the books arrived; nothing delivered", playerId);
			return;
		}

		if (error != null) {
			send(player, describe(error), ChatFormatting.RED);
			return;
		}

		reportSkipped(player, plan.skipped());

		if (plan.books().isEmpty()) {
			send(player, "Yeni kitap yok.", ChatFormatting.GRAY);
			return;
		}

		// The player may have moved or broken the chest while we were waiting.
		Optional<AcceptChestFinder.Found> found = findChest(player);
		if (found.isEmpty()) {
			send(player, SilverfishMod.ACCEPT_CHEST_NAME + " sandığı artık yakında değil; kitaplar konmadı.",
					ChatFormatting.RED);
			return;
		}

		Container chest = found.get().container();
		List<String> placed = new ArrayList<>();
		int slot = 0;
		for (LibraryServiceClient.Book book : plan.books()) {
			slot = nextEmptySlot(chest, slot);
			if (slot < 0) {
				break;
			}
			chest.setItem(slot, BookFactory.create(book));
			placed.add(book.id());
		}
		chest.setChanged();

		int notFitting = plan.books().size() - placed.size();
		if (placed.isEmpty()) {
			send(player, "%s sandığı dolu; %d kitap sığmadı.".formatted(SilverfishMod.ACCEPT_CHEST_NAME, notFitting),
					ChatFormatting.RED);
			return;
		}

		String message = "%d kitap %s sandığına konuldu.".formatted(placed.size(), SilverfishMod.ACCEPT_CHEST_NAME);
		if (notFitting > 0) {
			message += " %d kitap sığmadı; sandığı boşaltıp tekrar K'ya bas.".formatted(notFitting);
		}
		send(player, message, notFitting > 0 ? ChatFormatting.YELLOW : ChatFormatting.GREEN);

		confirm(server, playerId, placed);
	}

	private void confirm(MinecraftServer server, UUID playerId, List<String> placed) {
		service.confirm(placed).whenComplete((accepted, error) -> {
			if (error == null) {
				SilverfishMod.LOGGER.info("Service recorded {} of {} delivered books", accepted, placed.size());
				return;
			}
			SilverfishMod.LOGGER.error("Could not confirm delivered books {}", placed, error);
			server.execute(() -> {
				ServerPlayer player = server.getPlayerList().getPlayer(playerId);
				if (player != null) {
					send(player, "Kitaplar kondu ama servise bildirilemedi; bir sonraki K'da aynı kitaplar "
							+ "tekrar gelebilir. (" + describe(error) + ")", ChatFormatting.YELLOW);
				}
			});
		});
	}

	private void reportSkipped(ServerPlayer player, List<LibraryServiceClient.Skipped> skipped) {
		if (skipped.isEmpty()) {
			return;
		}
		send(player, skipped.size() + " dosya atlandı:", ChatFormatting.YELLOW);
		skipped.stream().limit(MAX_SKIPPED_LINES).forEach(s ->
				send(player, " - " + s.file() + ": " + s.reason(), ChatFormatting.GRAY));
		if (skipped.size() > MAX_SKIPPED_LINES) {
			send(player, " ... ve " + (skipped.size() - MAX_SKIPPED_LINES) + " dosya daha", ChatFormatting.GRAY);
		}
	}

	/** Turns an exception from the HTTP call into a message a player can act on. */
	private String describe(Throwable error) {
		if (hasCause(error, ConnectException.class)) {
			return "Servis kapalı görünüyor (%s). service klasöründe uvicorn'u başlat: "
					.formatted(service.baseUrl())
					+ "python -m uvicorn --factory mclibrary.app:create_app --port 8765";
		}
		if (hasCause(error, HttpTimeoutException.class)) {
			return "Servis %d saniye içinde yanıt vermedi.".formatted(service.timeout().toSeconds());
		}
		Throwable root = rootCause(error);
		if (root instanceof LibraryServiceClient.ServiceException) {
			return root.getMessage();
		}
		SilverfishMod.LOGGER.error("Book request failed", error);
		return "Servisle konuşurken hata oluştu: " + root.getClass().getSimpleName()
				+ (root.getMessage() != null ? " (" + root.getMessage() + ")" : "");
	}

	private static boolean hasCause(Throwable error, Class<? extends Throwable> type) {
		for (Throwable t = error; t != null; t = t.getCause()) {
			if (type.isInstance(t)) {
				return true;
			}
		}
		return false;
	}

	private static Throwable rootCause(Throwable error) {
		Throwable t = error;
		while (t.getCause() != null && t.getCause() != t) {
			t = t.getCause();
		}
		return t;
	}

	private static Optional<AcceptChestFinder.Found> findChest(ServerPlayer player) {
		return AcceptChestFinder.find(player, SilverfishMod.SEARCH_RADIUS, SilverfishMod.ACCEPT_CHEST_NAME);
	}

	private static int nextEmptySlot(Container container, int from) {
		for (int i = from; i < container.getContainerSize(); i++) {
			if (container.getItem(i).isEmpty()) {
				return i;
			}
		}
		return -1;
	}

	private static void send(ServerPlayer player, String message, ChatFormatting color) {
		player.sendSystemMessage(Component.literal(message).withStyle(color));
	}
}
