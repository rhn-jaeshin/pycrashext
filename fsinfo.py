"""
 Written by Daniel Sungju Kwon
"""

from __future__ import print_function
from __future__ import division

from pykdump.API import *
from LinuxDump import Tasks
import sys
import operator

import crashcolor


def dentry_to_filename (dentry) :
    if (dentry == 0):
        return "<>"

    try:
        crashout = exec_crash_command ("files -d {:#x}".format(dentry))
        filename = crashout.split()[-1]
        if filename == "DIR" :
            filename = "<blank>"
        return filename
    except:
        return "<invalid>"


def get_vfsmount_from_sb(sb):
    if (sb == 0):
        return -1

    try:
        crashout_list = exec_crash_command("mount")
        for mount_line in crashout_list.splitlines():
            mount_details = mount_line.split()
            if (mount_details[1] == ("%x" % sb)):
                return int(mount_details[0], 16)
    except:
        return -1

    return -1

def get_mount_option(mnt_flags):
    return {
        0x01: "nosuid",         # "MNT_NOSUID",
        0x02: "nodev",          # "MNT_NODEV",
        0x04: "noexec",         # "MNT_NOEXEC",
        0x08: "noatime",        # "MNT_NOATIME",
        0x10: "nodiratime",     # "MNT_NODIRATIME",
        0x20: "",               # "MNT_RELATIME",
        0x40: "ro",             # "MNT_READONLY",

# Below looks too much information, so, not visible for now
#        0x100: "SHRINKABLE",
#        0x200: "WRITE_HOLD",
#        0x1000: "SHARED",
#        0x2000: "UNBINDABLE",

        0x800000: "locked",     # MNT_LOCKED
        0x8000000: "umount",    # MNT_UMOUNT
    }.get(mnt_flags, "")

def get_mount_options(mnt_flags):
    result = ""
    for x in range(0, 64):
        option = get_mount_option((mnt_flags & (1 << x)))
        if (option != "" and result != ""):
            result = result + ","
        result = result + option

    return result

def get_frozen_str(frozen_type):
    return {
        0: "SB_UNFROZEN",
        1: "SB_FREEZE_WRITE",
        2: "SB_FREEZE_PAGEFAULT",
        3: "SB_FREEZE_FS",
        4: "SB_FREEZE_COMPLETE",
        -1: "UNRECOGNIZED STATE",
    }[frozen_type]


def all_filesystem_info(options):
    super_blocks = sym2addr("super_blocks")
    for sb in readSUListFromHead(super_blocks,
                                         "s_list",
                                         "struct super_block"):
        frozen = -1
        if (member_offset('struct super_block', 's_writers') >= 0):
            frozen = sb.s_writers.frozen
        elif (member_offset('struct super_block', 's_frozen') >= 0):
            frozen = sb.s_frozen

        frozen_str = get_frozen_str(frozen)

        vfsmnt_addr = get_vfsmount_from_sb(sb)
        mnt_flags = 0
        if (vfsmnt_addr != -1):
            vfsmnt = readSU("struct vfsmount", vfsmnt_addr)
            mnt_flags = vfsmnt.mnt_flags


        if frozen_str != "SB_UNFROZEN":
            crashcolor.set_color(crashcolor.LIGHTRED)
        print ("SB: 0x%14x, frozen=%s, %s (%s) [%s], (%s)" %
               (sb, frozen_str,
               dentry_to_filename(sb.s_root), sb.s_id,
                sb.s_type.name,
                get_mount_options(mnt_flags)))
        crashcolor.set_color(crashcolor.RESET)


def find_pid_from_file(options):
    file_struct = readSU("struct file",
                         int(options.file_addr_for_pid, 16))
    d_inode = file_struct.f_path.dentry.d_inode;
    find_pid_from_inode(d_inode);


def find_pid_from_dentry(options):
    dentry = readSU("struct dentry",
                    int(options.dentry_addr_for_pid, 16))
    d_inode = dentry.d_inode;
    find_pid_from_inode(d_inode);


def find_pid_from_inode(d_inode):
    vfs_inode_offset = member_offset('struct proc_inode', 'vfs_inode');
    proc_inode = readSU("struct proc_inode", d_inode - vfs_inode_offset)
    pid_first = proc_inode.pid.tasks[0].first
    pids_offset = member_offset("struct task_struct", "pids");
    task_struct = readSU("struct task_struct", pid_first - pids_offset);

    crashout = exec_crash_command(
        "struct task_struct.pid,comm,files {:#x} -d".format(task_struct))
    print("struct task_struct.pid,comm,files %x\n%s" %
          (task_struct, crashout))

    return

O_RDONLY = 0x0
O_WRONLY = 0x1
O_RDWR = 0x2
O_ACCMODE = 0x3

def get_file_open_mode_str(f_mode):
    result_str = ""
    if ((f_mode & 0x03) == O_RDONLY):
        result_str = result_str + "Read-Only"
    if ((f_mode & 0x03) == O_WRONLY):
        result_str = result_str + "Write-Only"
    if ((f_mode & 0x03) == O_RDWR):
        result_str = result_str + "Read/Write"

    return result_str


def show_inode_details(options):
    inode = readSU("struct inode", int(options.inode, 16))
    dentry_offset = member_offset('struct dentry',
                                  'd_alias')
    i_dentry_size = member_size("struct inode", "i_dentry")
    hlist_head_sz = struct_size("struct hlist_head")
    if i_dentry_size == hlist_head_sz:
        dentry_addr = inode.i_dentry.first - dentry_offset
    else:
        dentry_addr = inode.i_dentry.next - dentry_offset

    if dentry_addr != -dentry_offset: # No dentry for this inode
        dentry = readSU('struct dentry', dentry_addr)
        dentry_details = exec_crash_command("files -d 0x%x" % (dentry))
        print(dentry_details)

    print("inode = 0x%x" % inode)
    i_sb = inode.i_sb
    print("i_sb = 0x%x : %s" % (i_sb, i_sb.s_id))
    address_space = inode.i_mapping
    print("address_space = 0x%x nrpages = %d = %d bytes" % (address_space, address_space.nrpages, (address_space.nrpages * 4096)))
    i_op_sym = exec_crash_command("sym %x" % (inode.i_op))
    print("inode operations = 0x%s" % (i_op_sym), end='')
    print("")
    print("%s" % (get_inode_details(inode)))


def get_inode_details(inode):
    try:
        i_uid = inode.i_uid.val
        i_gid = inode.i_gid.val
    except:
        i_uid = inode.i_uid
        i_gid = inode.i_gid

    return "file size = %d bytes, ino = %d, link count = %d\n\tuid = %d, gid = %d" %\
          (inode.i_size, inode.i_ino, inode.i_nlink, i_uid, i_gid)


def show_file_details(options):
    file = readSU("struct file", int(options.file, 16))
    dentry_details = exec_crash_command("files -d 0x%x" % (file.f_path.dentry))
    print("== File Info ==")
    print(dentry_details)

    print("file = 0x%x" % file)
    i_sb = file.f_inode.i_sb
    print("i_sb = 0x%x : %s" % (i_sb, i_sb.s_id))
    address_space = file.f_mapping
    print("address_space = 0x%x nrpages = %d = %d bytes" % (address_space, address_space.nrpages, (address_space.nrpages * 4096)))
    print("")

    f_op_sym = exec_crash_command("sym %x" % (file.f_op))
    print("file operations = %s" % (f_op_sym), end='')
    mount_details = exec_crash_command("mount").splitlines()
    mount_str = "%x" % (file.f_path.dentry.d_sb)
    print("file open mode = %s (0x%x)" % (get_file_open_mode_str(file.f_flags), file.f_flags))
    print("%s" % (get_inode_details(file.f_inode)))
    print("")
    found = False
    for mount_line in mount_details:
        words = mount_line.split()
        if words[1] == mount_str:
            if found == False:
                print("== Mount Info ==")
            print(mount_line)
            found = True


def show_slab_dentry(options):
    result_lines = exec_crash_command("kmem -S dentry").splitlines()
    sb_dict = {}
    for line in result_lines:
        if line.startswith("  ["):
            dentry_addr = int(line[3:-1], 16)
            dentry   = readSU("struct dentry", dentry_addr)
            if dentry.d_sb not in sb_dict:
                sb_dict[dentry.d_sb] = 0
            sb_dict[dentry.d_sb] = sb_dict[dentry.d_sb] + 1
            if options.show_details:
                print("0x%x %s" % (dentry_addr, dentry_to_filename(dentry_addr)))

    print("\nsuberblock usage summary")
    print("=" * 30)
    print("%16s %8s %s" % ("super_block", "count", "root"))
    print("-" * 30)
    sorted_sb_dict = sorted(sb_dict.items(),
                            key=operator.itemgetter(1), reverse=True)
    total_count = 0
    for sb, count in sorted_sb_dict:
        print("0x%x %5d %s" %
              (sb, count, dentry_to_filename(sb.s_root)))
        total_count = total_count + count
    print("-" * 40)
    print("Total allocated object count = %d" % (total_count))
    print("=" * 40)


def show_caches(options):
    shrinker_list = readSymbol("shrinker_list")
    if shrinker_list == None or shrinker_list == 0:
        return

    sb_offset = member_offset("struct super_block", "s_shrink")
    if sb_offset < 0:
        return

    total_dentry_unused = 0
    total_inodes_unused = 0
    prune_super = sym2addr("prune_super")

    print("=" * 60)
    print("%18s %10s %10s %s" %\
          ("super_block", "dentries", "inodes", "path"))
    print("-" * 60)
    for shrinker in readSUListFromHead(shrinker_list,
                                       "list",
                                       "struct shrinker"):
        # Only concerns about normal super_block
        if shrinker.shrink != prune_super:
            continue

        sb = readSU("struct super_block", shrinker - sb_offset)
        dentry_unused = sb.s_nr_dentry_unused
        inodes_unused = sb.s_nr_inodes_unused
        if dentry_unused == 0 and inodes_unused == 0:
            continue
        total_dentry_unused = total_dentry_unused + dentry_unused
        total_inodes_unused = total_inodes_unused + inodes_unused

        print("0x%x %10d %10d %s" %\
              (sb, dentry_unused, inodes_unused,
               dentry_to_filename(sb.s_root)))

    print("-" * 60)
    print("%18s %10d %10d" %\
          ("Total", total_dentry_unused, total_inodes_unused))



def fsinfo():
    op = OptionParser()
    op.add_option("-d", "--details", dest="show_details", default=0,
                  action="store_true",
                  help="Show detailed information")
    op.add_option("-f", "--file", dest="file", default="",
                  action="store",
                  help="Show detailed file information for 'struct file' address (hex)")
    op.add_option("-i", "--inode", dest="inode", default="",
                  action="store",
                  help="Show detailed inode information for 'struct inode' address (hex)")
    op.add_option("-s", "--slab", dest="show_slab", default=0,
                  action="store_true",
                  help="Show all 'dentry' details in slab")
    op.add_option("-c", "--caches", dest="show_caches", default=0,
                  action="store_true",
                  help="Show dentry/inodes caches")
    op.add_option("--findpidbyfile", dest="file_addr_for_pid", default="",
                  action="store",
                  help="Find PID from a /proc file address (hex)")
    op.add_option("--findpidbydentry", dest="dentry_addr_for_pid",
                  default="", action="store",
                  help="Find PID from a /proc dentry address (hex)")

    (o, args) = op.parse_args()

    if (o.file_addr_for_pid != ""):
        find_pid_from_file(o)
        sys.exit(0);
    if (o.dentry_addr_for_pid != ""):
        find_pid_from_dentry(o)
        sys.exit(0);
    if (o.file != ""):
        show_file_details(o)
        sys.exit(0)
    if (o.inode != ""):
        show_inode_details(o)
        sys.exit(0)
    if (o.show_slab):
        show_slab_dentry(o)
        sys.exit(0)
    if (o.show_caches):
        show_caches(o)
        sys.exit(0)


    all_filesystem_info(o)

if ( __name__ == '__main__'):
    fsinfo()
