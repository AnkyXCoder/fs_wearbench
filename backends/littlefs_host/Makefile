# Makefile for the host LittleFS emubd wear runner.
#
# LITTLEFS_ROOT may be overridden to point to a littlefs tree:
#   make LITTLEFS_ROOT=/path/to/littlefs

CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -std=c11 -DLFS_NO_ASSERT
LITTLEFS_ROOT ?= ../../../os/modules/fs/littlefs

LFS_SRCS := \
	$(LITTLEFS_ROOT)/lfs.c \
	$(LITTLEFS_ROOT)/lfs_util.c \
	$(LITTLEFS_ROOT)/bd/lfs_emubd.c \
	$(LITTLEFS_ROOT)/bd/lfs_filebd.c \
	$(LITTLEFS_ROOT)/bd/lfs_rambd.c

INCS := -I$(LITTLEFS_ROOT)

.PHONY: all clean

all: wear_littlefs

wear_littlefs: main.c $(LFS_SRCS)
	$(CC) $(CFLAGS) $(INCS) -o $@ $^

clean:
	rm -f wear_littlefs
