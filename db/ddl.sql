CREATE TABLE `history` (
  `id` int NOT NULL,
  `busted` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `hash` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `game_datetime` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci


CREATE TABLE `case_3` (
  `id` int NOT NULL,
  `count` smallint DEFAULT NULL,
  `busted` int NOT NULL,
  `dead_flg` tinyint DEFAULT NULL,
  `game_datetime` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci


CREATE TABLE `case_5` (
  `id` int NOT NULL,
  `count` smallint DEFAULT NULL,
  `busted` int NOT NULL,
  `dead_flg` tinyint DEFAULT NULL,
  `game_datetime` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci


CREATE TABLE `case_7` (
  `id` int NOT NULL,
  `count` smallint DEFAULT NULL,
  `busted` int NOT NULL,
  `dead_flg` tinyint DEFAULT NULL,
  `game_datetime` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci


CREATE TABLE `case_10` (
  `id` int NOT NULL,
  `count` smallint DEFAULT NULL,
  `busted` int NOT NULL,
  `dead_flg` tinyint DEFAULT NULL,
  `game_datetime` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci