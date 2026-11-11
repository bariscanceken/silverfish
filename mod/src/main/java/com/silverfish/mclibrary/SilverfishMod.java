package com.silverfish.mclibrary;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.networking.v1.PayloadTypeRegistry;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.fabricmc.loader.api.FabricLoader;

public class SilverfishMod implements ModInitializer {
	public static final String MOD_ID = "silverfish_mclibrary";
	public static final Logger LOGGER = LoggerFactory.getLogger(MOD_ID);

	/** Players look for the accept chest within this many blocks. */
	public static final int SEARCH_RADIUS = 32;
	/** Name given to the chest with an anvil (compared ignoring case and surrounding spaces). */
	public static final String ACCEPT_CHEST_NAME = "Kabul";

	@Override
	public void onInitialize() {
		ModConfig config = ModConfig.load(FabricLoader.getInstance().getConfigDir());
		LOGGER.info("Library service: {} (timeout {}s)", config.serviceUrl(), config.timeoutSeconds());
		BookDelivery delivery = new BookDelivery(new LibraryServiceClient(config));

		PayloadTypeRegistry.serverboundPlay().register(RequestBooksPayload.TYPE, RequestBooksPayload.CODEC);

		// Fabric runs play payload handlers on the server thread, so the world is safe to read here.
		ServerPlayNetworking.registerGlobalReceiver(RequestBooksPayload.TYPE,
				(payload, context) -> delivery.request(context.server(), context.player()));
	}
}
