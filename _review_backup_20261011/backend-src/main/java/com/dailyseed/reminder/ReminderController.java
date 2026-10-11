package com.dailyseed.reminder;

import com.dailyseed.user.DeviceUserResolver;
import java.nio.charset.StandardCharsets;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

/**
 * 日历提醒文件的下载口（设计文档 §8.1，接口总表 §11 的 {@code GET /api/reminder.ics}）。
 *
 * <p>⚠️ 前端**必须用 fetch 取这个接口再自己存文件**，不能写成
 * {@code <a href="/api/reminder.ics">}：身份只靠 {@code X-Device-Id} 请求头，
 * 而浏览器点链接时带不上它 —— 后端会以 400「缺少请求头」拒掉（这个坑踩过一次，见交接简报 §5）。
 */
@RestController
public class ReminderController {

    private final ReminderService service;
    private final DeviceUserResolver resolver;

    public ReminderController(ReminderService service, DeviceUserResolver resolver) {
        this.service = service;
        this.resolver = resolver;
    }

    @GetMapping(value = "/api/reminder.ics", produces = "text/calendar;charset=UTF-8")
    public ResponseEntity<byte[]> ics(@RequestHeader("X-Device-Id") String deviceId) {
        byte[] body = service.ics(resolver.require(deviceId)).getBytes(StandardCharsets.UTF_8);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(new MediaType("text", "calendar", StandardCharsets.UTF_8));
        // 带文件名下载才有"存下来"的感觉；文件名用 ASCII，免得不同浏览器把中文名弄乱
        headers.setContentDisposition(ContentDisposition.attachment().filename("dailyseed.ics").build());
        return new ResponseEntity<>(body, headers, org.springframework.http.HttpStatus.OK);
    }
}
