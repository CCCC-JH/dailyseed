package com.dailyseed.explored;

import com.dailyseed.user.DeviceUserResolver;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 探索记录（设计文档 §3.2 / 接口总表 §11）。
 *
 * <p>只有一个接口，而且是**只读**的：这一页没有"做了什么"要提交，
 * 也没有"该探索几张了"要判定——那会是监工（红线 1）。
 */
@RestController
@RequestMapping("/api/explored")
public class ExploredController {

    private final ExploredService service;
    private final DeviceUserResolver resolver;

    public ExploredController(ExploredService service, DeviceUserResolver resolver) {
        this.service = service;
        this.resolver = resolver;
    }

    /** 走过的全部探索卡，新的在前 */
    @GetMapping
    public ExploredService.ExploredView explored(@RequestHeader("X-Device-Id") String deviceId) {
        return service.explored(resolver.require(deviceId));
    }
}
