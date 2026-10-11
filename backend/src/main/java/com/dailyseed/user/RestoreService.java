package com.dailyseed.user;

import java.util.Optional;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 「用同步码找回数据」（设计文档 §7.2）。
 *
 * <p>这条路存在的理由很具体：清缓存时 {@code deviceId} 和同步码**一起**消失，
 * 后端认不出你是谁——所以补发物理上无法送达，唯一能做的就是"趁他还不在乎时先塞给他一次"
 * （§6.4），以及**在他真的换了设备时，让这串码管用**。
 *
 * <p>这里有两条刻意的规则，都是产品决定而不是技术限制：
 * <ol>
 *   <li><b>不许"给自己恢复"</b>：这台设备已经被认识，那它没有丢失任何东西。
 *       放行只会让用户困惑"为什么同一台手机还要恢复一次"，所以直接拒掉。</li>
 *   <li><b>成功即换发新码</b>：旧码立即作废（§7.2「可重置」）。这样"码被别人看到过一次"
 *       这件事有个干净的补救办法，用户在新设备上也能立刻拿到一份新凭据抄下来。</li>
 * </ol>
 */
@Service
public class RestoreService {

    /** 同步码的规范形态是 `K7M2-P9QX`：8 个有效字符 + 第 5 位一个连字符（见 UserStore.newSyncCode） */
    static final int SYNC_CODE_LENGTH = 8;
    static final int SYNC_CODE_DASH_AT = 4;

    private final UserStore users;

    public RestoreService(UserStore users) {
        this.users = users;
    }

    @Transactional
    public Optional<UserStore.Restored> restore(String rawSyncCode, String deviceId) {
        String syncCode = canonicalSyncCode(rawSyncCode);
        if (syncCode.length() != SYNC_CODE_LENGTH + 1) {
            return Optional.empty();
        }
        // 已经是"熟人"了，没有可恢复的东西（见类注释第 1 条）
        if (users.findUserIdByDevice(deviceId).isPresent()) {
            throw new IllegalStateException("这台设备已经认识你了，不用恢复");
        }
        return users.restoreBySyncCode(syncCode, deviceId);
    }

    // ==================== 纯函数（可单测，不连数据库） ====================

    /**
     * 把用户抄回来的码整理成**落库时的规范形态**：`K7M2-P9QX`。
     *
     * <p>用户从截图或纸上抄回来时，很容易带上空格、大小写不一、漏掉或重复连字符；
     * 这些都是同一串码，不该让人重抄一遍。
     *
     * <p>⚠️ <b>连字符必须补回去，不能抹掉</b>。库里的 {@code sync_code_hash} 哈希的是
     * {@link UserStore#newSyncCode()} 生成的那串**带连字符**的字符；抹成 8 位裸码去查会恒定查不到，
     * 症状是"码明明对着，却永远说没有这个码"——这个坑踩过一次，别再踩。
     *
     * <p>只认"正好 8 个有效字符"，多一个少一个都不猜：猜出来的码等于放宽凭据强度。
     */
    static String canonicalSyncCode(String raw) {
        String bare = bareSyncCode(raw);
        if (bare.length() != SYNC_CODE_LENGTH) {
            return "";
        }
        return bare.substring(0, SYNC_CODE_DASH_AT) + "-" + bare.substring(SYNC_CODE_DASH_AT);
    }

    /**
     * 去掉分隔符与空白、转大写，只剩字母数字本体。
     *
     * <p>⚠️ <b>不要写成 {@code replaceAll("[^0-9A-Za-z]", "")}</b>：在 Unicode 感知的字符类语义下
     * {@code [^…]} 里的隐式 {@code \w} 会把**全角空格 {@code \u3000} 当成字母数字**，于是它躲过剥离、
     * 让长度多出一位，用户明明抄对了却被判"位数不对"。这里逐个字符**白名单**判断：
     * 只接受 ASCII 字母数字（顺带转大写），其余一律丢掉。
     */
    static String bareSyncCode(String raw) {
        if (raw == null) {
            return "";
        }
        StringBuilder sb = new StringBuilder(raw.length());
        for (char c : raw.toCharArray()) {
            if ((c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z')) {
                sb.append(c);
            } else if (c >= 'a' && c <= 'z') {
                sb.append(Character.toUpperCase(c));
            }
        }
        return sb.toString();
    }

    /** 给人看的分组形态；输入可以是任何写法。前端也用同一套分组规则 */
    static String displaySyncCode(String raw) {
        String bare = bareSyncCode(raw);
        return bare.length() <= SYNC_CODE_DASH_AT
                ? bare
                : bare.substring(0, SYNC_CODE_DASH_AT) + "-" + bare.substring(SYNC_CODE_DASH_AT);
    }
}
