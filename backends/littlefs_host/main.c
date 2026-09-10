/*
 * Host LittleFS wear profiler using lfs_emubd.
 *
 * Compile with the littlefs source files:
 *   gcc -O2 -Ilittlefs -I. main.c littlefs/lfs.c littlefs/lfs_util.c \
 *       littlefs/bd/lfs_emubd.c littlefs/bd/lfs_filebd.c littlefs/bd/lfs_rambd.c \
 *       -o wear_littlefs
 */

#include "lfs.h"
#include "bd/lfs_emubd.h"

#include <getopt.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void usage(const char *prog) {
    fprintf(stderr,
            "Usage: %s [options]\n"
            "Options:\n"
            "  -b, --block-size       Block/erase size (default 4096)\n"
            "  -c, --block-count      Number of blocks (default 256)\n"
            "  -r, --read-size        Minimum read size (default 16)\n"
            "  -p, --prog-size        Minimum program size (default 16)\n"
            "  -C, --cache-size       LittleFS cache size (default 64)\n"
            "  -l, --lookahead-size   Lookahead size (default 16)\n"
            "  -B, --block-cycles     LittleFS block_cycles (default 512)\n"
            "  -s, --record-size      Record size in bytes (default 128)\n"
            "  -n, --record-count     Number of records to write (default 1000)\n"
            "  -f, --filename         File to write (default /sensor.log)\n"
            "  -o, --output           Output JSON file (default stdout)\n"
            "  -h, --help             Show this help\n",
            prog);
}

int main(int argc, char **argv) {
    uint32_t block_size = 4096;
    uint32_t block_count = 256;
    uint32_t read_size = 16;
    uint32_t prog_size = 16;
    uint32_t cache_size = 64;
    uint32_t lookahead_size = 16;
    int32_t  block_cycles = 512;
    uint32_t record_size = 128;
    uint32_t record_count = 1000;
    const char *filename = "/sensor.log";
    const char *output_path = NULL;

    static const struct option long_options[] = {
        {"block-size", required_argument, 0, 'b'},
        {"block-count", required_argument, 0, 'c'},
        {"read-size", required_argument, 0, 'r'},
        {"prog-size", required_argument, 0, 'p'},
        {"cache-size", required_argument, 0, 'C'},
        {"lookahead-size", required_argument, 0, 'l'},
        {"block-cycles", required_argument, 0, 'B'},
        {"record-size", required_argument, 0, 's'},
        {"record-count", required_argument, 0, 'n'},
        {"filename", required_argument, 0, 'f'},
        {"output", required_argument, 0, 'o'},
        {"help", no_argument, 0, 'h'},
        {0, 0, 0, 0},
    };

    int c;
    while ((c = getopt_long(argc, argv, "b:c:r:p:C:l:B:s:n:f:o:h",
                            long_options, NULL)) != -1) {
        switch (c) {
        case 'b': block_size = (uint32_t)atoi(optarg); break;
        case 'c': block_count = (uint32_t)atoi(optarg); break;
        case 'r': read_size = (uint32_t)atoi(optarg); break;
        case 'p': prog_size = (uint32_t)atoi(optarg); break;
        case 'C': cache_size = (uint32_t)atoi(optarg); break;
        case 'l': lookahead_size = (uint32_t)atoi(optarg); break;
        case 'B': block_cycles = (int32_t)atoi(optarg); break;
        case 's': record_size = (uint32_t)atoi(optarg); break;
        case 'n': record_count = (uint32_t)atoi(optarg); break;
        case 'f': filename = optarg; break;
        case 'o': output_path = optarg; break;
        case 'h': usage(argv[0]); return 0;
        default: usage(argv[0]); return 1;
        }
    }

    if (block_size == 0 || block_count == 0 ||
        read_size == 0 || prog_size == 0 ||
        cache_size == 0 || record_size == 0) {
        fprintf(stderr, "Invalid zero-size parameter\n");
        return 1;
    }

    uint8_t *read_buffer = malloc(cache_size);
    uint8_t *prog_buffer = malloc(cache_size);
    uint8_t *lookahead_buffer = malloc(lookahead_size);
    if (!read_buffer || !prog_buffer || !lookahead_buffer) {
        fprintf(stderr, "Out of memory\n");
        return 1;
    }

    lfs_emubd_t emubd;
    struct lfs_emubd_config emubd_cfg = {
        .read_size = read_size,
        .prog_size = prog_size,
        .erase_size = block_size,
        .erase_count = block_count,
        .erase_value = 0xff,
        .erase_cycles = 0xffffffff,
        .badblock_behavior = LFS_EMUBD_BADBLOCK_PROGERROR,
        .power_cycles = 0,
        .powerloss_behavior = LFS_EMUBD_POWERLOSS_NOOP,
        .powerloss_cb = NULL,
        .powerloss_data = NULL,
        .track_branches = false,
        .disk_path = NULL,
        .read_sleep = 0,
        .prog_sleep = 0,
        .erase_sleep = 0,
    };

    struct lfs_config cfg = {
        .context = &emubd,
        .read = lfs_emubd_read,
        .prog = lfs_emubd_prog,
        .erase = lfs_emubd_erase,
        .sync = lfs_emubd_sync,
        .read_size = read_size,
        .prog_size = prog_size,
        .block_size = block_size,
        .block_count = block_count,
        .cache_size = cache_size,
        .lookahead_size = lookahead_size,
        .read_buffer = read_buffer,
        .prog_buffer = prog_buffer,
        .lookahead_buffer = lookahead_buffer,
        .block_cycles = block_cycles,
    };

    int err = lfs_emubd_create(&cfg, &emubd_cfg);
    if (err) {
        fprintf(stderr, "lfs_emubd_create failed: %d\n", err);
        return 1;
    }

    lfs_t lfs;
    err = lfs_format(&lfs, &cfg);
    if (err) {
        fprintf(stderr, "lfs_format failed: %d\n", err);
        return 1;
    }
    err = lfs_mount(&lfs, &cfg);
    if (err) {
        fprintf(stderr, "lfs_mount failed: %d\n", err);
        return 1;
    }

    uint8_t *record = malloc(record_size);
    if (!record) {
        fprintf(stderr, "Out of memory\n");
        return 1;
    }
    memset(record, 0xA5, record_size);

    lfs_file_t file;
    err = lfs_file_open(&lfs, &file, filename,
                        LFS_O_WRONLY | LFS_O_CREAT);
    if (err) {
        fprintf(stderr, "lfs_file_open failed: %d\n", err);
        return 1;
    }

    err = lfs_file_seek(&lfs, &file, 0, LFS_SEEK_END);
    if (err < 0) {
        fprintf(stderr, "lfs_file_seek failed: %d\n", err);
        return 1;
    }

    for (uint32_t i = 0; i < record_count; i++) {
        record[0] = (uint8_t)(i & 0xFF);
        lfs_ssize_t written = lfs_file_write(&lfs, &file, record, record_size);
        if (written != (lfs_ssize_t)record_size) {
            fprintf(stderr, "lfs_file_write failed at record %u: %d\n", i,
                    (int)written);
            return 1;
        }
    }

    err = lfs_file_close(&lfs, &file);
    if (err) {
        fprintf(stderr, "lfs_file_close failed: %d\n", err);
        return 1;
    }
    err = lfs_unmount(&lfs);
    if (err) {
        fprintf(stderr, "lfs_unmount failed: %d\n", err);
        return 1;
    }

    uint64_t user_bytes = (uint64_t)record_count * record_size;
    lfs_emubd_io_t readed = lfs_emubd_readed(&cfg);
    lfs_emubd_io_t proged = lfs_emubd_proged(&cfg);
    lfs_emubd_io_t erased = lfs_emubd_erased(&cfg);

    FILE *out = stdout;
    if (output_path) {
        out = fopen(output_path, "w");
        if (!out) {
            fprintf(stderr, "Cannot open %s\n", output_path);
            return 1;
        }
    }

    fprintf(out, "{\n");
    fprintf(out, "  \"backend\": \"littlefs_host\",\n");
    fprintf(out, "  \"config\": {\n");
    fprintf(out, "    \"block_size\": %u,\n", block_size);
    fprintf(out, "    \"block_count\": %u,\n", block_count);
    fprintf(out, "    \"read_size\": %u,\n", read_size);
    fprintf(out, "    \"prog_size\": %u,\n", prog_size);
    fprintf(out, "    \"cache_size\": %u,\n", cache_size);
    fprintf(out, "    \"lookahead_size\": %u,\n", lookahead_size);
    fprintf(out, "    \"block_cycles\": %d,\n", block_cycles);
    fprintf(out, "    \"record_size\": %u,\n", record_size);
    fprintf(out, "    \"record_count\": %u\n", record_count);
    fprintf(out, "  },\n");
    fprintf(out, "  \"metrics\": {\n");
    fprintf(out, "    \"user_bytes\": %llu,\n", (unsigned long long)user_bytes);
    fprintf(out, "    \"readed_bytes\": %llu,\n", (unsigned long long)readed);
    fprintf(out, "    \"proged_bytes\": %llu,\n", (unsigned long long)proged);
    fprintf(out, "    \"erased_bytes\": %llu\n", (unsigned long long)erased);
    fprintf(out, "  },\n");
    fprintf(out, "  \"per_block_wear\": [\n");

    int first = 1;
    for (lfs_block_t b = 0; b < (lfs_block_t)block_count; b++) {
        lfs_emubd_swear_t wear = lfs_emubd_wear(&cfg, b);
        if (wear == 0) {
            continue;
        }
        fprintf(out, "%s\n    {\"block\": %u, \"cycles\": %d}",
                first ? "" : ",", b, (int)wear);
        first = 0;
    }
    fprintf(out, "\n  ]\n");
    fprintf(out, "}\n");

    if (output_path) {
        fclose(out);
    }

    free(record);
    free(read_buffer);
    free(prog_buffer);
    free(lookahead_buffer);
    lfs_emubd_destroy(&cfg);

    return 0;
}
