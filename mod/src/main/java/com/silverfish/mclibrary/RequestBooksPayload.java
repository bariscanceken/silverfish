package com.silverfish.mclibrary;

import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.Identifier;

/** Client to server: "deliver my books to the accept chest". Carries no data. */
public record RequestBooksPayload() implements CustomPacketPayload {
	public static final RequestBooksPayload INSTANCE = new RequestBooksPayload();

	public static final CustomPacketPayload.Type<RequestBooksPayload> TYPE =
			new CustomPacketPayload.Type<>(Identifier.fromNamespaceAndPath(SilverfishMod.MOD_ID, "request_books"));

	public static final StreamCodec<RegistryFriendlyByteBuf, RequestBooksPayload> CODEC = StreamCodec.unit(INSTANCE);

	@Override
	public Type<? extends CustomPacketPayload> type() {
		return TYPE;
	}
}
