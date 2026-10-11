package com.dailyseed.user;

import com.dailyseed.ops.ActivityCounters;
import com.dailyseed.reminder.ReminderService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import java.security.SecureRandom;
import java.time.LocalTime;
import java.util.HexFormat;
import java.util.Optional;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

/**
 * 零注册：打开即用（设计文档 §7）。
 *
 * <p>{@code syncCode} 只在第一次创建时返回一次，之后服务端只留哈希；换设备靠它恢复。
 *
 * <p><b>身份有两条路</b>：正路是 {@code X-Device-Id}（localStorage 里那个），
 * 退路是 HttpOnly 的 {@link SessionCookie}。退路的适用面**故意很窄**——只有连 deviceId
 * 都拿不出来的时候才走它（见 {@link #create}）。
 */
@RestController
@RequestMapping("/api/session")
public class SessionController {

    /**
     * 由**服务端**补发的 deviceId，只在"靠 Cookie 认人、但客户端拿不出自己的 ID"时用。
     *
     * <p>前缀刻意不是 {@code dev-}：那是前端生成 ID 的记号，一眼就能分辨这个 ID 来自哪一侧。
     */
    private static final String SERVER_DEVICE_PREFIX = "srv-";

    private final SecureRandom random = new SecureRandom();

    /**
     * 新设备的入参。
     *
     * <p>⚠️ {@code deviceId} <b>刻意不加 {@code @NotBlank}</b>：清掉 localStorage 之后
     * 前端**根本生成不出 deviceId**，那时它只能发一个空值过来、由 Cookie 认人。
     * 加了校验，这条退路在第一道关口就被 400 掉，"清缓存还能找回"就成了空话。
     */
    public record Request(String deviceId) {
    }

    /** 恢复的入参：码 + 这台新设备的 deviceId（恢复的本质就是"把码绑到这台设备上"） */
    public record RestoreRequest(@NotBlank String syncCode, @NotBlank String deviceId) {
    }

    /**
     * @param userId    这个人是谁。前端读不到 HttpOnly Cookie，所以它**必须**在响应里给出来，
     *                  否则前端无从知道"我是被 Cookie 救回来的"
     * @param syncCode  为 null 表示这个设备已经用过，不必再弹一次同步码；
     *                  恢复时这里给的是**新码**（旧码已作废）
     * @param deviceId  <b>只有"服务端补发了一个 deviceId"时才有值</b>。Cookie 是 HttpOnly 的，
     *                  前端看不见里面的 userId，唯一能知道"换人了"的途径就是这里多出一个 ID——
     *                  收到它就请存进 localStorage，之后走正路。
     * @param recovered 这次是不是靠 Cookie 认出来的（前端只用来决定要不要提示一句）
     */
    public record Response(long userId, String syncCode, boolean created, String deviceId, boolean recovered) {
    }

    /** 只回码，不带 userId：恢复之后前端直接重载首屏，userId 对它没有意义 */
    public record RestoreResponse(String syncCode) {
    }

    public record ReminderRequest(@NotBlank String time) {
    }

    public record ReminderResponse(String time) {
    }

    private final UserStore users;
    private final RestoreService restore;
    private final ReminderService reminders;
    private final SessionCookie cookie;
    private final ActivityCounters counters;

    public SessionController(UserStore users, RestoreService restore, ReminderService reminders,
                             SessionCookie cookie, ActivityCounters counters) {
        this.users = users;
        this.restore = restore;
        this.reminders = reminders;
        this.cookie = cookie;
        this.counters = counters;
    }

    /**
     * 认设备 → （拿不出 deviceId 时）认 Cookie → 建新号。
     *
     * <p><b>为什么 Cookie 只在"deviceId 为空"时才生效</b>：前端生成了一个自己没见过的
     * deviceId，意思是"我要一个干净的开始"（用户清掉 localStorage 就会这样）。
     * 这时拿旧 Cookie 把人拽回旧花园，他就**永远没法重新开始**了——而他的旧身份此刻
     * 并没有丢（还在别的设备上、或者他有同步码）。真正会丢数据的只有一种情形：
     * **连 deviceId 都拿不出来**，而那正是这条退路唯一的入口。
     *
     * <p>实测教训：最初写成"deviceId 未被认识就用 Cookie 认"，结果是清 localStorage
     * 也会被拽回旧号——`tools/verify_cookie.py` 的第 6 条守着这个纠正。
     */
    @PostMapping
    public ResponseEntity<Response> create(
            @RequestHeader(value = "X-Device-Id", required = false) String deviceId,
            @RequestBody(required = false) Request body,
            HttpServletRequest httpRequest) {

        // 请求头优先，body 兜底（老客户端只发 body，别把它弄坏）
        Optional<String> claimed = nonBlank(deviceId)
                .or(() -> nonBlank(body == null ? null : body.deviceId()));

        // ① 正路：这个设备被认识
        if (claimed.isPresent()) {
            Optional<Long> known = users.findUserIdByDevice(claimed.get());
            if (known.isPresent()) {
                return remembered(new Response(known.get(), null, false, null, false), known.get());
            }
        }

        // ② 退路：连 deviceId 都没有，但浏览器还带着我们种下的 Cookie
        if (claimed.isEmpty()) {
            Optional<Long> byCookie = cookie.readUserId(httpRequest);
            if (byCookie.isPresent()) {
                long userId = byCookie.get();
                // 补一个 deviceId 交给前端存下来：Cookie 是 HttpOnly 的，前端读不到它，
                // 只能靠这个字段知道"我换了个人"，也才能在之后走回正路
                String issued = newDeviceId();
                users.attachDevice(userId, issued);
                counters.identityRecoveredByCookie(); // 退路真的救到人了，这条最值得看
                return remembered(new Response(userId, null, false, issued, true), userId);
            }
        }

        // ③ 真·新用户（deviceId 一定非空才可能走到这里）
        String fresh = claimed.orElseThrow(() -> new ResponseStatusException(
                HttpStatus.BAD_REQUEST, "deviceId 不能为空（这台设备也没有可用的身份凭据）"));
        UserStore.Session session = users.createAnonymous(fresh);
        counters.sessionCreated();
        return remembered(new Response(session.userId(), session.syncCode(), true, null, false),
                session.userId());
    }

    /**
     * 用同步码找回数据（设计文档 §7.2）。
     *
     * <p>三种失败刻意用三种状态码，因为它们对用户是三件不同的事：
     * <ul>
     *   <li><b>400</b>：码的位数就不对（"没抄全"）——根本没到"查"这一步</li>
     *   <li><b>404</b>：位数对但查不到（"抄错了"）</li>
     *   <li><b>409</b>：这台设备已经被认识（"你不需要恢复"）</li>
     * </ul>
     *
     * <p>404 而不是 400 是刻意的：前端把 400 理解为"缺少必需请求头"那个约定俗成的错
     * （不带 {@code X-Device-Id} 就是 400，见交接简报 §5），用它表示"码错了"会被误读成身份问题。
     */
    @PostMapping("/restore")
    public ResponseEntity<RestoreResponse> restore(@RequestBody @Valid RestoreRequest request) {
        if (RestoreService.bareSyncCode(request.syncCode()).length() != RestoreService.SYNC_CODE_LENGTH) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "同步码是 8 位，像 K7M2-P9QX 这样");
        }
        try {
            UserStore.Restored restored = this.restore.restore(request.syncCode(), request.deviceId())
                    .orElseThrow(() -> new ResponseStatusException(
                            HttpStatus.NOT_FOUND, "没有这个同步码，再对一遍？"));
            // ★ 恢复之后这条 Cookie 必须跟着换人，否则下次清缓存会被领回**上一个**账号
            counters.sessionRecovered();
            return remembered(new RestoreResponse(restored.syncCode()), restored.userId());
        } catch (IllegalStateException e) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, e.getMessage());
        }
    }

    /**
     * 用户自己设的提醒时间（设计文档 §8.1）。**把时间存下来是"他做过承诺"的凭证**，
     * 下次下载 .ics 时用它；不存的话用户每次下载都得重选一遍。
     */
    @PostMapping("/reminder")
    public ReminderResponse setReminder(@RequestHeader("X-Device-Id") String deviceId,
                                       @RequestBody @Valid ReminderRequest request) {
        LocalTime time = ReminderService.parseTime(request.time())
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.BAD_REQUEST, "时间要写成 HH:mm，比如 08:00"));
        users.updateRemindAt(requireUserId(deviceId), time);
        return new ReminderResponse(time.format(ReminderService.HHMM));
    }

    private ResponseEntity<Response> remembered(Response body, long userId) {
        HttpHeaders headers = new HttpHeaders();
        cookie.remember(headers, userId);
        return new ResponseEntity<>(body, headers, HttpStatus.OK);
    }

    private ResponseEntity<RestoreResponse> remembered(RestoreResponse body, long userId) {
        HttpHeaders headers = new HttpHeaders();
        cookie.remember(headers, userId);
        return new ResponseEntity<>(body, headers, HttpStatus.OK);
    }

    private long requireUserId(String deviceId) {
        return users.findUserIdByDevice(deviceId)
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.UNAUTHORIZED, "先调 POST /api/session 建匿名身份"));
    }

    /** 服务端补发的 deviceId。只要求够唯一，不要求密码学强度（和前端那个同一个标准） */
    private String newDeviceId() {
        byte[] bytes = new byte[16];
        random.nextBytes(bytes);
        return SERVER_DEVICE_PREFIX + HexFormat.of().formatHex(bytes);
    }

    private static Optional<String> nonBlank(String value) {
        return value == null || value.isBlank() ? Optional.empty() : Optional.of(value.trim());
    }
}
