package com.dailyseed.assignment;

import com.dailyseed.user.DeviceUserResolver;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

/**
 * 补留：允许你回头，把过去没留的卡重新留下（设计文档 §3.3）。
 *
 * <p>窗口 3 天（含今天）。为什么是 3 天：既能救急（忘了点、或今天才真正做了），
 * 又避免任务堆砌——超过 3 天就让它过去，保持"每日"的节奏。
 */
@RestController
@RequestMapping("/api/history")
public class HistoryController {

    private final AssignmentService service;
    private final DeviceUserResolver resolver;

    public HistoryController(AssignmentService service, DeviceUserResolver resolver) {
        this.service = service;
        this.resolver = resolver;
    }

    /** 最近 N 天可补留的卡（N 上限 3，含今天） */
    @GetMapping
    public List<AssignmentService.HistoryItem> history(@RequestHeader("X-Device-Id") String deviceId,
                                                       @RequestParam(defaultValue = "3") int days) {
        return service.history(resolver.require(deviceId), days);
    }

    /** 补留：只有 3 天内、没留过、且不是放纵卡的才能补 */
    @PostMapping("/{assignmentId}/keep")
    public AssignmentService.HistoryItem keep(@RequestHeader("X-Device-Id") String deviceId,
                                              @PathVariable long assignmentId) {
        try {
            return service.keepPast(resolver.require(deviceId), assignmentId);
        } catch (IllegalArgumentException | IllegalStateException e) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, e.getMessage());
        }
    }
}
