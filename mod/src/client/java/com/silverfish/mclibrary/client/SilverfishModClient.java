package com.silverfish.mclibrary.client;

import com.mojang.blaze3d.platform.InputConstants;
import org.lwjgl.sdl.SDLScancode;

import net.minecraft.client.KeyMapping;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.keymapping.v1.KeyMappingHelper;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;

import com.silverfish.mclibrary.RequestBooksPayload;
import com.silverfish.mclibrary.SilverfishMod;

public class SilverfishModClient implements ClientModInitializer {
	// Shown in Controls as the translation of "key.category.silverfish_mclibrary.main".
	private static final KeyMapping.Category CATEGORY =
			KeyMapping.Category.register(Identifier.fromNamespaceAndPath(SilverfishMod.MOD_ID, "main"));

	private static KeyMapping deliverBooksKey;

	@Override
	public void onInitializeClient() {
		deliverBooksKey = KeyMappingHelper.registerKeyMapping(new KeyMapping(
				"key.silverfish_mclibrary.deliver_books",
				InputConstants.Type.KEYBOARD,
				SDLScancode.SDL_SCANCODE_K,
				CATEGORY));

		ClientTickEvents.END_CLIENT_TICK.register(client -> {
			while (deliverBooksKey.consumeClick()) {
				if (client.player == null) {
					continue;
				}
				if (ClientPlayNetworking.canSend(RequestBooksPayload.TYPE)) {
					ClientPlayNetworking.send(RequestBooksPayload.INSTANCE);
				} else {
					client.player.sendSystemMessage(Component.literal(
							"Bu sunucuda silverfish-mclibrary modu yüklü değil"));
				}
			}
		});
	}
}
