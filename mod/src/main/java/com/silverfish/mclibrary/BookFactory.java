package com.silverfish.mclibrary;

import java.util.List;

import net.minecraft.ChatFormatting;
import net.minecraft.core.component.DataComponents;
import net.minecraft.network.chat.Component;
import net.minecraft.server.network.Filterable;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.ItemLore;
import net.minecraft.world.item.component.WritableBookContent;
import net.minecraft.world.item.component.WrittenBookContent;

/** Turns a book from the service into a written book item. */
public final class BookFactory {
	private BookFactory() {
	}

	public static ItemStack create(LibraryServiceClient.Book book) {
		// The service already respects these limits; clamp anyway so a bad response
		// can never produce an item the game rejects.
		String title = clamp(book.title(), WrittenBookContent.TITLE_MAX_LENGTH);
		List<Filterable<Component>> pages = book.pages().stream()
				.limit(WritableBookContent.MAX_PAGES)
				.map(page -> Filterable.<Component>passThrough(Component.literal(clamp(page, WrittenBookContent.PAGE_LENGTH))))
				.toList();

		ItemStack stack = new ItemStack(Items.WRITTEN_BOOK);
		stack.set(DataComponents.WRITTEN_BOOK_CONTENT, new WrittenBookContent(
				Filterable.passThrough(title),
				book.author(),
				0, // generation: original
				pages,
				true)); // plain literal text, nothing to resolve
		stack.set(DataComponents.LORE, new ItemLore(List.of(
				Component.literal(book.source()).withStyle(ChatFormatting.GRAY))));
		return stack;
	}

	private static String clamp(String text, int max) {
		return text.length() <= max ? text : text.substring(0, max);
	}
}
