package com.dailyseed.garden;

import com.dailyseed.user.DeviceUserResolver;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

/**
 * 花园这一页的两个动作（设计文档 §11）。
 *
 * <p>只有两个接口：看一眼 + 宣布毕业。**没有"该毕业了"的接口**——那是产品明令不要的判定。
 */
@RestController
@RequestMapping("/api/garden")
public class GardenController {

    private final GardenService service;
    private final DeviceUserResolver resolver;

    public GardenController(GardenService service, DeviceUserResolver resolver) {
        this.service = service;
        this.resolver = resolver;
    }

    /** 我的花园：留住的每一张习惯卡（各留了几次）+ 已内化清单 */
    @GetMapping
    public GardenService.GardenView garden(@RequestHeader("X-Device-Id") String deviceId) {
        return service.garden(resolver.require(deviceId));
    }

    /**
     * 「它已经是我的习惯了」。
     *
     * <p>入口可见但绝不催促（前端在小标记出现后才画这个按钮，§6.1）；
     * **重复调用不报错**——用户手抖点两次不该看到红字（幂等，验收 ②）。
     */
    @PostMapping("/{cardId}/graduate")
    public GardenPlant graduate(@RequestHeader("X-Device-Id") String deviceId,
                                @PathVariable long cardId) {
        try {
            return service.graduate(resolver.require(deviceId), cardId);
        } catch (IllegalArgumentException | IllegalStateException e) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, e.getMessage());
        }
    }
}
