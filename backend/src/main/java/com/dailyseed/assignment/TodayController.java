package com.dailyseed.assignment;

import com.dailyseed.user.DeviceUserResolver;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

/**
 * 「今天」这一页的三个动作（设计文档 §11：接口极少）。
 *
 * <p>身份用设备 ID（{@code X-Device-Id}），不信任前端传来的 userId。
 */
@RestController
@RequestMapping("/api")
public class TodayController {

    private final AssignmentService service;
    private final DeviceUserResolver resolver;

    public TodayController(AssignmentService service, DeviceUserResolver resolver) {
        this.service = service;
        this.resolver = resolver;
    }

    /** 今天的一粒种子：懒生成 + 幂等，同一天反复调返回同一张（**未揭晓时仍是卡背**） */
    @GetMapping("/today")
    public AssignmentService.TodayView today(@RequestHeader("X-Device-Id") String deviceId) {
        return service.today(resolver.require(deviceId));
    }

    /**
     * 抽：第一次抽 = 揭晓当天那张；之后每次 = 换掉当天那张（重抽）。
     *
     * <p>{@code getView=true} 只读当前状态（前端刷新用），不消耗配额、不换卡。
     */
    @PostMapping("/today/draw")
    public AssignmentService.TodayView draw(@RequestHeader("X-Device-Id") String deviceId,
                                           @RequestParam(required = false, defaultValue = "false") boolean getView) {
        try {
            return service.draw(resolver.require(deviceId), getView);
        } catch (IllegalArgumentException | IllegalStateException e) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, e.getMessage());
        }
    }

    public record KeepRequest(String note) {
    }

    /** 唯一的核心交互：留着 */
    @PostMapping("/today/keep")
    public AssignmentService.TodayView keep(@RequestHeader("X-Device-Id") String deviceId,
                                           @RequestBody(required = false) KeepRequest body) {
        long userId = resolver.require(deviceId);
        try {
            return service.keep(userId, body == null ? null : body.note());
        } catch (IllegalArgumentException | IllegalStateException e) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, e.getMessage());
        }
    }

    /** 今天想放纵：把今天换成一张放纵卡（门槛不公示，满足才出现入口） */
    @PostMapping("/today/indulge")
    public AssignmentService.TodayView indulge(@RequestHeader("X-Device-Id") String deviceId) {
        try {
            return service.indulge(resolver.require(deviceId));
        } catch (IllegalArgumentException | IllegalStateException e) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, e.getMessage());
        }
    }
}
