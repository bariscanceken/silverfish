package com.silverfish.mclibrary;

import java.util.Optional;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;

import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.networking.v1.PayloadTypeRegistry;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;

public class SilverfishMod implements ModInitializer {
	public static final String MOD_ID = "silverfish_mclibrary";
	public static final Logger LOGGER = LoggerFactory.getLogger(MOD_ID);

	/** Players look for the accept chest within this many blocks. */
	public static final int SEARCH_RADIUS = 32;
	/** Name given to the chest with an anvil. */
	public static final String ACCEPT_CHEST_NAME = "Kabul";

	@Override
	public void onInitialize() {
		PayloadTypeRegistry.serverboundPlay().register(RequestBooksPayload.TYPE, RequestBooksPayload.CODEC);

		// Fabric runs play payload handlers on the server thread, so the world is safe to read here.
		ServerPlayNetworking.registerGlobalReceiver(RequestBooksPayload.TYPE,
				(payload, context) -> onRequestBooks(context.player()));
	}

	private static void onRequestBooks(ServerPlayer player) {
		Optional<AcceptChestFinder.Found> found =
				AcceptChestFinder.find(player, SEARCH_RADIUS, ACCEPT_CHEST_NAME);

		if (found.isEmpty()) {
			player.sendSystemMessage(Component.literal("Yakında " + ACCEPT_CHEST_NAME + " sandığı yok"));
			return;
		}

		AcceptChestFinder.Found chest = found.get();
		BlockPos pos = chest.pos();
		player.sendSystemMessage(Component.literal(
				"%s sandığı bulundu: %d %d %d (%d boş yuva)".formatted(
						ACCEPT_CHEST_NAME, pos.getX(), pos.getY(), pos.getZ(), chest.emptySlots())));
	}
}
