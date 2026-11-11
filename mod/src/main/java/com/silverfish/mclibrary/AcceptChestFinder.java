package com.silverfish.mclibrary;

import java.util.Map;
import java.util.Optional;

import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.Container;
import net.minecraft.world.level.block.ChestBlock;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.entity.ChestBlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.LevelChunk;

/** Finds the nearest chest renamed (with an anvil) to a given name. Must run on the server thread. */
public final class AcceptChestFinder {
	private AcceptChestFinder() {
	}

	/**
	 * @param pos       position of the named chest block
	 * @param container the whole inventory; for a double chest both halves (54 slots)
	 */
	public record Found(BlockPos pos, Container container) {
		public int emptySlots() {
			int empty = 0;
			for (int i = 0; i < container.getContainerSize(); i++) {
				if (container.getItem(i).isEmpty()) {
					empty++;
				}
			}
			return empty;
		}
	}

	public static Optional<Found> find(ServerPlayer player, int radius, String name) {
		ServerLevel level = player.level();
		BlockPos center = player.blockPosition();
		long maxDistSq = (long) radius * radius;

		Found best = null;
		long bestDistSq = Long.MAX_VALUE;

		int minChunkX = (center.getX() - radius) >> 4;
		int maxChunkX = (center.getX() + radius) >> 4;
		int minChunkZ = (center.getZ() - radius) >> 4;
		int maxChunkZ = (center.getZ() + radius) >> 4;

		for (int cx = minChunkX; cx <= maxChunkX; cx++) {
			for (int cz = minChunkZ; cz <= maxChunkZ; cz++) {
				// getChunkNow never loads or generates chunks; unloaded ones are skipped.
				LevelChunk chunk = level.getChunkSource().getChunkNow(cx, cz);
				if (chunk == null) {
					continue;
				}
				for (Map.Entry<BlockPos, BlockEntity> entry : chunk.getBlockEntities().entrySet()) {
					if (!(entry.getValue() instanceof ChestBlockEntity chest) || !hasName(chest, name)) {
						continue;
					}
					BlockPos pos = entry.getKey();
					long distSq = distSq(center, pos);
					if (distSq > maxDistSq || distSq >= bestDistSq) {
						continue;
					}
					Container container = containerOf(level, pos, chest);
					if (container != null) {
						best = new Found(pos, container);
						bestDistSq = distSq;
					}
				}
			}
		}
		return Optional.ofNullable(best);
	}

	private static boolean hasName(ChestBlockEntity chest, String name) {
		Component custom = chest.getCustomName();
		return custom != null && custom.getString().strip().equals(name);
	}

	/** Returns the combined inventory for a double chest, the chest itself otherwise (may be null). */
	private static Container containerOf(ServerLevel level, BlockPos pos, ChestBlockEntity chest) {
		BlockState state = level.getBlockState(pos);
		if (state.getBlock() instanceof ChestBlock chestBlock) {
			// ignoreBlocked = true: a cat or a block on the lid must not hide the chest.
			return ChestBlock.getContainer(chestBlock, state, level, pos, true);
		}
		return chest;
	}

	private static long distSq(BlockPos a, BlockPos b) {
		long dx = a.getX() - b.getX();
		long dy = a.getY() - b.getY();
		long dz = a.getZ() - b.getZ();
		return dx * dx + dy * dy + dz * dz;
	}
}
