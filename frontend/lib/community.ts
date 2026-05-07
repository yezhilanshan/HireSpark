'use client'

export type PostItem = {
    id: string
    author: string
    avatar: string
    title: string
    content: string
    tags: string[]
    likes: number
    comments: number
    isOfficial: boolean
    createdAt: number
}

export type CommentItem = {
    id: string
    postId: string
    author: string
    avatar: string
    content: string
    likes: number
    createdAt: number
}

export type StudyGroup = {
    id: string
    name: string
    description: string
    tags: string[]
    memberCount: number
    maxMembers: number
    createdBy: string
    createdAt: number
    members: string[]
}

const POSTS_KEY = 'hirespark.community.posts.v1'
const COMMENTS_KEY = 'hirespark.community.comments.v1'
const GROUPS_KEY = 'hirespark.community.groups.v1'
const LIKED_POSTS_KEY = 'hirespark.community.likedPosts.v1'

function read<T>(key: string, fallback: T): T {
    try {
        const raw = localStorage.getItem(key)
        if (!raw) return fallback
        const parsed = JSON.parse(raw)
        return Array.isArray(parsed) ? (parsed as T) : fallback
    } catch {
        return fallback
    }
}

function write<T>(key: string, value: T) {
    try {
        localStorage.setItem(key, JSON.stringify(value))
    } catch {
        // ignore
    }
}

// Posts
export function getPosts(): PostItem[] {
    return read<PostItem[]>(POSTS_KEY, [])
}

export function addPost(
    author: string,
    avatar: string,
    title: string,
    content: string,
    tags: string[],
    isOfficial = false
): PostItem {
    const posts = getPosts()
    const newPost: PostItem = {
        id: `post_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        author,
        avatar,
        title,
        content,
        tags,
        likes: 0,
        comments: 0,
        isOfficial,
        createdAt: Date.now(),
    }
    posts.unshift(newPost)
    write(POSTS_KEY, posts)
    return newPost
}

export function likePost(postId: string): boolean {
    const liked = read<string[]>(LIKED_POSTS_KEY, [])
    if (liked.includes(postId)) {
        // unlike
        const next = liked.filter((id) => id !== postId)
        write(LIKED_POSTS_KEY, next)
        const posts = getPosts()
        const post = posts.find((p) => p.id === postId)
        if (post) {
            post.likes = Math.max(0, post.likes - 1)
            write(POSTS_KEY, posts)
        }
        return false
    }
    liked.push(postId)
    write(LIKED_POSTS_KEY, liked)
    const posts = getPosts()
    const post = posts.find((p) => p.id === postId)
    if (post) {
        post.likes += 1
        write(POSTS_KEY, posts)
    }
    return true
}

export function hasLikedPost(postId: string): boolean {
    const liked = read<string[]>(LIKED_POSTS_KEY, [])
    return liked.includes(postId)
}

export function getPostById(postId: string): PostItem | undefined {
    return getPosts().find((p) => p.id === postId)
}

// Comments
export function getCommentsForPost(postId: string): CommentItem[] {
    return read<CommentItem[]>(COMMENTS_KEY, [])
        .filter((c) => c.postId === postId)
        .sort((a, b) => a.createdAt - b.createdAt)
}

export function addComment(
    postId: string,
    author: string,
    avatar: string,
    content: string
): CommentItem {
    const comments = read<CommentItem[]>(COMMENTS_KEY, [])
    const newComment: CommentItem = {
        id: `comment_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        postId,
        author,
        avatar,
        content,
        likes: 0,
        createdAt: Date.now(),
    }
    comments.push(newComment)
    write(COMMENTS_KEY, comments)

    const posts = getPosts()
    const post = posts.find((p) => p.id === postId)
    if (post) {
        post.comments += 1
        write(POSTS_KEY, posts)
    }
    return newComment
}

// Study Groups
export function getGroups(): StudyGroup[] {
    return read<StudyGroup[]>(GROUPS_KEY, getDefaultGroups())
}

function getDefaultGroups(): StudyGroup[] {
    return [
        {
            id: 'group_default_1',
            name: 'Java 后端春招冲刺群',
            description: '面向 2025 届春招的 Java 后端学习小组，每日打卡、周周模拟面试。',
            tags: ['Java', '后端', '春招'],
            memberCount: 128,
            maxMembers: 200,
            createdBy: 'PanelMind 官方',
            createdAt: Date.now() - 1000 * 60 * 60 * 24 * 30,
            members: [],
        },
        {
            id: 'group_default_2',
            name: '前端进阶修炼营',
            description: 'React、Vue、Node.js 全栈前端进阶，项目实战驱动学习。',
            tags: ['前端', 'React', 'Vue'],
            memberCount: 86,
            maxMembers: 150,
            createdBy: 'PanelMind 官方',
            createdAt: Date.now() - 1000 * 60 * 60 * 24 * 20,
            members: [],
        },
        {
            id: 'group_default_3',
            name: '算法每日一题',
            description: 'LeetCode 每日一题打卡，互相监督，共同进步。',
            tags: ['算法', 'LeetCode', '数据结构'],
            memberCount: 256,
            maxMembers: 300,
            createdBy: 'PanelMind 官方',
            createdAt: Date.now() - 1000 * 60 * 60 * 24 * 45,
            members: [],
        },
    ]
}

export function createGroup(
    name: string,
    description: string,
    tags: string[],
    maxMembers: number,
    createdBy: string
): StudyGroup {
    const groups = getGroups()
    const newGroup: StudyGroup = {
        id: `group_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        name,
        description,
        tags,
        memberCount: 1,
        maxMembers,
        createdBy,
        createdAt: Date.now(),
        members: [createdBy],
    }
    groups.unshift(newGroup)
    write(GROUPS_KEY, groups)
    return newGroup
}

export function joinGroup(groupId: string, userName: string): boolean {
    const groups = getGroups()
    const group = groups.find((g) => g.id === groupId)
    if (!group) return false
    if (group.members.includes(userName)) return false
    if (group.memberCount >= group.maxMembers) return false
    group.members.push(userName)
    group.memberCount += 1
    write(GROUPS_KEY, groups)
    return true
}

export function leaveGroup(groupId: string, userName: string): boolean {
    const groups = getGroups()
    const group = groups.find((g) => g.id === groupId)
    if (!group) return false
    if (!group.members.includes(userName)) return false
    group.members = group.members.filter((m) => m !== userName)
    group.memberCount = Math.max(1, group.memberCount - 1)
    write(GROUPS_KEY, groups)
    return true
}

export function isGroupMember(groupId: string, userName: string): boolean {
    const group = getGroups().find((g) => g.id === groupId)
    return group ? group.members.includes(userName) : false
}

export function getGroupById(groupId: string): StudyGroup | undefined {
    return getGroups().find((g) => g.id === groupId)
}

// Seed demo posts
export function seedDemoPosts() {
    const posts = getPosts()
    if (posts.length > 0) return

    addPost(
        'PanelMind 官方',
        '',
        '面试复盘：如何优雅地回答"你的缺点是什么"？',
        '这个问题几乎是每场 HR 面的必考题。很多候选人会直接说"我工作太拼了"这种假缺点，反而让面试官觉得不真诚。\n\n建议的回答框架：\n1. 选择一个真实的、但不会影响岗位核心能力的缺点\n2. 说明你已经在如何改进\n3. 展示改进后的成果\n\n例如："我过去在公开演讲时会比较紧张，为了改善这一点，我主动报名了公司的技术分享会，现在已经能从容地在 50 人面前做技术分享了。"',
        ['面经', 'HR面', '技巧'],
        true
    )

    addPost(
        '小明',
        '',
        '字节跳动后端一面复盘',
        '今天刚面完字节后端，趁热打铁写个复盘。\n\n**考察点：**\n1. Redis 持久化机制（RDB vs AOF）\n2. MySQL 索引优化，给一个慢查询让分析\n3. 手撕 LRU Cache\n4. 分布式锁的实现方案\n\n**感受：** 面试官很 nice，不会的地方会引导。手撕代码要求比较高，需要边界条件考虑清楚。\n\n**准备建议：** 多刷 LeetCode 中等题，八股文要理解原理而不是背答案。',
        ['字节跳动', '后端', '面经'],
        false
    )

    addPost(
        '后端小王',
        '',
        'Spring Bean 生命周期面试题整理',
        '整理了 Spring Bean 生命周期的面试回答要点，分享给大家：\n\n1. 实例化（Instantiation）\n2. 属性赋值（Populate）\n3. 初始化（Initialization）\n   - 调用 Aware 接口方法\n   - 调用 BeanPostProcessor.postProcessBeforeInitialization\n   - 调用 @PostConstruct / init-method\n   - 调用 BeanPostProcessor.postProcessAfterInitialization\n4. 使用（In Use）\n5. 销毁（Destruction）\n   - @PreDestroy / destroy-method\n\n建议结合源码和实际项目经验来回答，不要只背流程。',
        ['Spring', 'Java', '八股文'],
        false
    )
}
