package com.dailyseed.ops;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * {@code GET /api/health}——不需要身份，一条请求说清这套服务现在能不能见人。
 *
 * <p>状态码就是结论：**200 = 可以接流量，503 = 别接**。正文里是全部探测项的明细，
 * 方便人肉排查时不用再登机器跑一遍 SQL。
 *
 * <p>为什么不放在 {@code /actuator/health}：那需要额外引 spring-boot-starter-actuator，
 * 而这里要的只是"六个探测项 + 一组计数"，一个 Controller 比引一整个监控栈更合适
 * （设计原则：模块化单体，不引不必要的依赖）。
 */
@RestController
@RequestMapping("/api/health")
public class HealthController {

    private static final Logger log = LoggerFactory.getLogger(HealthController.class);

    private final HealthService service;

    public HealthController(HealthService service) {
        this.service = service;
    }

    @GetMapping
    public ResponseEntity<HealthService.Report> health() {
        HealthService.Report report = service.report();
        if (!report.ok()) {
            // 只记首次出现的失败原因，避免探活被反复打时把日志刷满
            log.warn("健康检查未通过：{}", report.checks().stream()
                    .filter(c -> !c.ok())
                    .map(c -> c.name() + " → " + c.detail())
                    .toList());
        }
        return new ResponseEntity<>(report, report.ok() ? HttpStatus.OK : HttpStatus.SERVICE_UNAVAILABLE);
    }
}
